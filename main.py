import openai
import os
import csv
import concurrent.futures
from docx import Document
import configparser
from wp import WordPress

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Read values from the configuration file
openai.api_key = config.get('openai', 'api_key')
model_name = config.get('openai', 'model')
add_credits = config.get('openai', 'add_credits')
credit_text = config.get('openai', 'credit_text')
# Access WordPress configuration
wp_username = config.get('wordpress', 'username')
wp_password = config.get('wordpress', 'password')
wp_post_status = config.get('wordpress', 'post_status')
wp_web_address = config.get('wordpress', 'site')



def get_ai_response(prompt, system_message) :
    #print(f"Getting AI response for...{prompt}")
    messages = [{"role": "developer", "content": system_message}, {"role": "user", "content": prompt}]
    # result = openai.chat.completions.create(model=model, messages=messages, temperature=0.5, max_tokens=1500) 
    result = openai.chat.completions.create(model=model_name, messages=messages) 
    print(f"AI response received for...{prompt}")
    return result.choices[0].message.content


def process_input_csv_file(input_csv_file):
    #print("Processing input CSV file...")
    data = []
    
    with open(input_csv_file, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            # only continue when the row is not empty
            if not any(row.values()):
                continue
            # Specifically check if 'topics' field is empty or not
            if not row['TOPICS'].strip():
                # If 'topics' field is empty, jump to the next row
                continue
                
            # Extract the columns for each row
            topics = row['TOPICS'].strip()
            authors = row['AUTHOR'].strip()
            categories = row['CATEGORIES'].strip()
            tags = row['TAGS'].strip()
            # Append the extracted data to the data list
            data.append({ 
                'topics': topics,
                'authors': authors,
                'categories': categories,
                'tags': tags
            })
    print("Input CSV file processed.")
    return data


def read_and_prepare_chatgpt_system_message(system_message_file):
    with open(system_message_file, 'r') as file:
        system_message = file.read()
    system_message_rules = "\n Rule:\n 1.The first row you generate should be a concise and impactful title for this article.\n 2.Start with the actual title right away, no need to put stuff like 'Title:' in front."
    return system_message + system_message_rules

def get_or_create_author(author_name, author_cache, WordPress):
    """
    Check if an author exists in the cache and return their ID.
    If not in cache, get/create the author in WordPress and update the cache.

    :param author_name: The name of the author to check/create.
    :param author_cache: A dictionary to cache author names and their IDs.
    :param WordPress: An instance of the class managing WordPress operations.
    :return: The ID of the author.
    """
    # Ensure consistent key usage by stripping whitespace
    author_name = author_name.strip()

    # Check if the author is already in the cache
    if author_name in author_cache:
        # Use the cached author ID
        return author_cache[author_name]
    else:
        # Author not in cache, so make an HTTP request to get/create the author
        author_id = WordPress.get_or_create_taxonomy_term('users', author_name)
        # Cache the result for future use
        author_cache[author_name] = author_id
        return author_id



def prepare_post_data(ai_response,author,category,tag,WordPress):
    # prepare the post_data
    lines = ai_response.split('\n') # Splitting the response into lines
    title = lines[0] # Assuming the first line is the title         
    paragraphs_list = lines[1:] # The rest of the lines are article            
    # Check if the add_credits flag is "yes" and append the string credit_text
    if add_credits.lower() == 'yes':   
        paragraphs_list.append(f"\n({credit_text})")  # Append the string to the end of the article
        article = '\n'.join(paragraphs_list) # Rejoin as a string  
        if wp_post_status.lower() == 'publish':
            post_data = {'title': title,'content': article,'author': author,'categories': category,'tags': tag, 'status':"publish"}
        else:
            post_data = {'title': title,'content': article,'author': author,'categories': category,'tags': tag}
        # Because there may be multiple tags or categories from the input file, need to get their ID one by one
        tags_list = post_data['tags'].split(',')  # Splitting tags into a list
        categories_list = post_data['categories'].split(',') # Splitting categories into a list

        # Check if tags_list effectively represents an empty list of tags
        if tags_list == [''] or not any(tag.strip() for tag in tags_list):
            post_data['tags'] = []
        else:
            # Process each tag to get their IDs if tags_list is not effectively empty
            tag_ids = [WordPress.get_or_create_taxonomy_term('tags', tag.strip()) for tag in tags_list if tag.strip()]
            post_data['tags'] = tag_ids

         # Check if categories_list effectively represents an empty list of tags
        if categories_list == [''] or not any(category.strip() for category in categories_list):
            #post_data['categories'] = []            
            # if default category is not set, there will be an error clicking the post's URL generated
            category_ids = [WordPress.get_or_create_taxonomy_term('categories', "Uncategorized")] 
            post_data['categories'] = category_ids
        else:
            # Process each tag to get their IDs if tags_list is not effectively empty
            category_ids = [WordPress.get_or_create_taxonomy_term('categories', category.strip()) for category in categories_list if category.strip()]
            post_data['categories'] = category_ids

    return post_data    
    

def main(input_file_name,system_message_file):
    wp = WordPress(wp_username, wp_password, wp_web_address)

    rows = process_input_csv_file(input_file_name) #read each row of the csv file
   
    # Initialize an empty dictionary to cache author IDs
    author_cache = {}
    # Loop over each row and extract data into respective lists
    prompts, authors, categories, tags = [], [], [], []
    for row in rows:
        prompts.append(row['topics'])
        categories.append(row['categories'])
        tags.append(row['tags'])
        # Extract and process the author using the new independent function
        row['authors'] = get_or_create_author(row['authors'], author_cache, wp)
        authors.append(row['authors'])

    # Reading system message file...
    system_message = read_and_prepare_chatgpt_system_message(system_message_file)
    print("System prompts file read.\n")

    
    # Create a ThreadPoolExecutor to handle tasks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Create a list of tuples, each containing data to be processed by a task
        data_for_executor = [( system_message, prompt, author, category, tag) for prompt, author, category, tag in zip(prompts, authors, categories, tags)]
        # Submit tasks to the executor and keep track of them using a dictionary
        future_to_data = {executor.submit(get_ai_response, prompt, system_prompt): (system_prompt, prompt, author, category, tag) for ( system_prompt, prompt, author, category, tag) in data_for_executor}
        for future in concurrent.futures.as_completed(future_to_data):
            (system_prompt,prompt,author, category, tag) = future_to_data[future]            
            try:
                ai_response = future.result()
                post_data = prepare_post_data(ai_response,author,category,tag,wp)                              
                                      
                wp.post_to_WordPress(post_data)
                print(f"Topic: {prompt} processed.\n")
            except Exception as exc:
                print(f'Generating output for {prompt} generated an exception: {exc}\n')
    print("ThreadPoolExecutor finished.")
    print("\nAI_Questioning_WP Completed!!!!\n")


try:
    main('input.csv','system_prompt.txt')
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    input("press ENTER to exit...")