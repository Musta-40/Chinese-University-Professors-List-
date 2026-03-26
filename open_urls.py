import webbrowser
import time
import os

def open_urls_from_file(filename="dmu_urls.txt", url_limit=50, delay_seconds=3):
    """
    Reads URLs from a file and opens them in new browser tabs.

    Args:
        filename (str): The name of the file containing the URLs.
        url_limit (int): The maximum number of URLs to open.
        delay_seconds (int): The delay in seconds between opening each URL.
    """
    # Check if the file exists before attempting to open it
    if not os.path.exists(filename):
        print(f"Error: The file '{filename}' was not found.")
        print("Please create a file named 'urls.txt' and add your URLs, one per line.")
        return

    print(f"Opening up to {url_limit} URLs from '{filename}' with a {delay_seconds}-second delay between each.")

    try:
        with open(filename, 'r') as file:
            urls = file.readlines()

            # Process only the first 'url_limit' URLs
            for i, url in enumerate(urls[:url_limit]):
                url = url.strip()  # Remove leading/trailing whitespace, including the newline character
                if url:  # Ensure the line is not empty
                    print(f"Opening URL {i + 1}/{len(urls)}: {url}")
                    webbrowser.open_new_tab(url)
                    # Pause between each URL to prevent overwhelming the browser or system
                    time.sleep(delay_seconds)

            print("\nFinished opening URLs.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# This block ensures the code runs only when the script is executed directly
if __name__ == "__main__":
    open_urls_from_file()
