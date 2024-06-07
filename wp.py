import requests
import json
import base64
import sys

class WordPress:
    # The __init__ method initializes a new instance of the WordPress class.
    def __init__(self, username, password, base_url):
        # Store the username, password, and base URL for the WordPress site.
        self.username = username
        self.password = password
        self.base_url = base_url
        
        # Concatenate username and password to form credentials.
        credentials = f"{username}:{password}"
        # Encode the credentials using base64 to use in the authorization header.
        token = base64.b64encode(credentials.encode())
        # Create the header that will be used for authentication in all requests.
        self.header = {'Authorization': 'Basic ' + token.decode('utf-8')}

        # Check authentication
        self.verify_authentication()

    
    # Perform a simple request to verify authentication credentials.
    # This method makes a GET request to /users/me, which is a standard endpoint in the WordPress REST API for fetching the details of the currently authenticated user.
    def verify_authentication(self):
        url = f"{self.base_url}/users/me"
        try:
            response = requests.get(url, headers=self.header)
            response.raise_for_status()
            print("Authentication successful.")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                print(f"\nAuthentication error: Please check your username and password.\n")
                sys.exit("Exiting due to authentication failure.")
            else:
                print(f"HTTP Error: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")


    # This method checks if a taxonomy term exists, and creates it if it doesn't.
    def get_or_create_taxonomy_term(self, term_type, term_name):
        term_name = term_name.strip()
        if term_type == "users" and not term_name:
             print("\n***ERROR***: Author is blank. Please provide a valid Author for all rows.\n")
             sys.exit("Error: Author is blank. Exiting....")
        # if the value is blank, do to call REST API to get json as it will return all tags or categories.
        if not term_name: 
            return

        # Send a GET request to search for the taxonomy term by name.
        print(f"{self.base_url}/{term_type}?search={term_name}")
        try:
            response = requests.get(f"{self.base_url}/{term_type}?search={term_name}", headers=self.header)
            response.raise_for_status()
            terms = response.json()  # Parse the response JSON to get the term data.
        except requests.exceptions.HTTPError as e:
            print(f"Error {response.status_code}: {response.text}")
            sys.exit
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            sys.exit

        # As WP do not use precise searching. It may have multiple results. Filter terms for an exact match
        exact_terms = [term for term in terms if term['name'].lower() == term_name.lower()]

        # If the term exists, print its ID and return it.
        if exact_terms:
            print(f"{term_type[:-1].capitalize()} '{term_name}' found with ID:{exact_terms[0]['id']}")        
            return exact_terms[0]['id']
        else:
            if term_type == "users":
                print(f"\n***ATTENTION***: User {term_name} does not exist, please create this user in the WordPress admin console.\n")
                sys.exit(f"Error: User {term_name} does not exist. Exiting....")
            else:
                # If the term doesn't exist, create a new term with the given name.
                term_data = {'name': term_name}
                # Send a POST request to create the term.
                creation_response = requests.post(f"{self.base_url}/{term_type}", headers=self.header, json=term_data)
                creation_response.raise_for_status()  # Ensure the request was successful.
                new_term_id = creation_response.json()['id']
                # Print the ID of the newly created term and return it.
                print(f"New {term_type[:-1].capitalize()} '{term_name}' created with ID: {new_term_id}")
                return new_term_id

    # This method posts new content to WordPress.
    def post_to_WordPress(self, data):
        # The endpoint URL for creating a new post.
        url = f"{self.base_url}/posts"
        try:
            # Send a POST request with the provided data to create a new post.
            response = requests.post(url, headers=self.header, json=data)
            response.raise_for_status()  # Check if the response status code indicates success.
            #print(f"wordpress response: {response.json()}")  # Print the response data as JSON.
            
            return response.text  # Return the text content of the response.
        except requests.exceptions.RequestException as e:
            # Print any errors that occur during the request.
            print(f"Error: {e}")
            print(f"data posted is {data}")
            return None
