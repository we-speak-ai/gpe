from urllib.request import urlopen
import requests
import re
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import MACHINE_CONFIG
import newspaper
import uuid
import requests
from bs4 import BeautifulSoup
import scraper_prompts
import MACHINE_CONFIG
import json
from groq import Groq
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

CONFIG_PATH = "mbh-config.json"

def is_iterable(variable):
    try:
        iter(variable)
        return True
    except TypeError:
        return False
    
def has_common_element(list1, list2):
    # Convert both lists to sets
    set1 = set(list1)
    set2 = set(list2)
    
    # Check if there is any intersection between the sets
    return not set1.isdisjoint(set2)

def scroll_and_extract(url, loadtime=10, max_lenght=100, headless = True, scrolls=100):
    # Set up Selenium WebDriver
    service = Service(ChromeDriverManager().install())  # Automatically handles ChromeDriver installation
    options = Options()
    if headless: options.add_argument("--headless")
    driver = webdriver.Chrome(service=service, options=options)
    found_urls = set()
    scroled = 0
    try:
        #-------------------------------------------------------------------------------------------------
        # Open the web page
        driver.get(url)
        prev_lenght = -1
        time.sleep(2)
        while prev_lenght < len(found_urls) and len(found_urls) < max_lenght:  # Adjust the range for more or less scrolling
            prev_lenght = len(found_urls)
            #-------------------------------------------------------------------------------------------------
            # Scrolling 
            for _ in range(scrolls):
                ActionChains(driver).scroll_by_amount(0, 1000).perform()
            scroled = scroled +1
            time.sleep(loadtime)  # Sleep to allow the page to load more content if needed
            #-------------------------------------------------------------------------------------------------
            # Extract the page content after scrolling
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            #-------------------------------------------------------------------------------------------------
            # Attach new links to set
            links = soup.find_all('a')
            for link in links:
                link = link.get('href')
                if link:
                    if not link in found_urls:
                        found_urls.add(link)
    finally:
        # Close the browser
        driver.quit()
    return found_urls

def get_articles(config: dict, max_url = 1000, output_path=None, verbal=False):
    """
     * config:
        * "url": The url to the site
        * "green_flag": [list of str] the news categories like: science, histrory, etc.
        * "red_flag": [list of str] The keywords that represent exclusion pages like author, category
        * "min_article_lenght": [int] how long shoud an article be at least to count as an article
        * "cfp": [bool] Chategory come first, mean that the article url looks like this telex.hu/scinece/big-science-discovery
        * "no_prefix": [bool] if true then we will not look for flags, both red and green flag are means exclusion!
    """
    base_url            = config["url"]                 if "url"                in config else False
    green_flag          = config["green_flag"]          if "green_flag"         in config else False
    red_flag            = config["red_flag"]            if "red_flag"           in config else False
    min_article_lenght  = config["min_article_lenght"]  if "min_article_lenght" in config else False
    cfp                 = config["cfp"]                 if "cfp"                in config else False
    no_prefix           = config["no_prefix"]           if "no_prefix"          in config else False
    html_class          = config["html_class"]          if "html_class"         in config else False
    numeric_pattern     = config["numeric_pattern"]     if "numeric_pattern"    in config else False
    headers             = config["headers"]             if "headers"            in config else False
    serial_in_html      = config["serial_in_html"]      if "serial_in_html"     in config else False
    dynamic             = config["dynamic"]             if "dynamic"            in config else False
    load_time           = config["load_time"]           if "load_time"          in config else MACHINE_CONFIG.LOAD_TIME
    scrolls             = config["scrolls"]             if "scrolls"            in config else MACHINE_CONFIG.SCROLLS
    headless            = config["headless"]            if "headless"           in config else MACHINE_CONFIG.HEADLESS
    fixed_path          = config["fixed_path"]          if "fixed_path"         in config else False

    visited_urls = set()
    articles = set()
    urls_to_visit = deque([base_url])

    # Function to check if a URL belongs to the base domain
    def is_same_domain(url, base_domain):
        return urlparse(url).netloc == base_domain

    # Starting the crawl
    while urls_to_visit and len(articles)<max_url and len(visited_urls)<max_url*100:
        current_url = urls_to_visit.popleft()
        
        # Skip if already visited
        if current_url in visited_urls:
            continue
        
        # Mark as visited
        visited_urls.add(current_url)
        if verbal: print(f"Visiting: {current_url}")
        
        try:
            response = requests.get(current_url) # , headers=headers
            encoding = response.encoding
            
            if response.status_code == 200:
                if dynamic:
                    links = scroll_and_extract(current_url, load_time, max_url, headless, scrolls)
                    filtered_links = [urljoin(base_url, link) for link in links if not ( link is None) and urljoin(base_url, link).startswith(base_url)]
                else:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = soup.find_all('a')
                    filtered_links = [s.get('href') for s in links if (not( s.get('href') is None) and (s.get('href').startswith('/') or s.get('href').startswith(base_url)))]
                if verbal:
                    print(f"\tAvailable: {len(links)} >> Filtered: {len(filtered_links)}")
                    for link in links:
                        print(f"\t\t- {link.get('href')}")
                for link in filtered_links:
                    if link:
                        #-----------------------------------------------------------------------------
                        # URL construction
                        good_link = []
                        full_url = urljoin(base_url, link)
                        parsed_url = urlparse(full_url)
                        path = parsed_url.path
                        segments = [segment for segment in path.split('/') if segment]
                        if is_same_domain(full_url, urlparse(base_url).netloc):
                            urls_to_visit.append(full_url)
                        #-----------------------------------------------------------------------------
                        # Filter urls-s
                        
                        if no_prefix:
                            # Example: https://reasonstobecheerful.world/living-seed-bank-preserving-amazon-biodiversity/
                            # good cases:
                            #   1: len(segments) == 1
                            #   2: not segment in [red or green]
                            #   3: len(segments[0])>=min_article_lenght
                            good_link.append(not(has_common_element(red_flag + green_flag, segments)) and len(segments)==1 and len(segments[0])>=min_article_lenght)
                            
                        if fixed_path:
                            found_fixed_path = False
                            for flag in green_flag:
                                if flag in path:
                                    found_fixed_path = True
                            good_link.append(found_fixed_path)


                        if cfp:
                            # Example_1: https://www.positive.news/environment/a-summary-of-the-ipcc-report/
                            # Example_2: https://www.positive.news/economics/good-business/how-catapult-uk-towards-solar-energy/
                            # good cases:
                            #   1: len(segments) > 1
                            #   2: segment[0] in green
                            #   3: not segment[0] in red
                            #   4: len(segments[-1])>=min_article_lenght

                            good_link.append(len(segments)>1 and segments[0] in green_flag and not(segments[0] in red_flag) and len(segments[-1])>=min_article_lenght)

                        if len(red_flag) !=0:
                            found_flag = any([ bool(flag in segments) for flag in red_flag ])
                            good_link.append(not found_flag)

                        if html_class:
                            link_response = requests.get(full_url)
                            html_content = link_response.text
                            soup = BeautifulSoup(html_content, 'html.parser')
                            tags = soup.select(html_class)
                            if tags is None or len(tags) == 0:
                                good_link.append(False)
                            else:
                                good_link.append(True)
                        if numeric_pattern: 
                            # Example_1: https://goodblacknews.org/2023/06/16/apple-adds-25-million-to-racial-equity-and-justice-initiative-increasing-financial-commitment-to-over-200m-since-2020/
                            # good cases:
                            #   1: url has date in it: example : 1999/12/15 ~ '/(\d{4})/(\d{2})/(\d{2})/'
                            #   2: len(segments[-1])>=min_article_lenght
                            # Search for the date pattern in the URL
                            match = re.search(numeric_pattern, full_url)
                            if match:
                                # Get the portion of the URL following the matched date
                                post_date_section = full_url[match.end():]
                                # Check if the remaining part after the date is longer than min_article_lenght characters
                                good_link.append(len(post_date_section) > 10)

                        if len(good_link) !=0 and all(good_link):
                            articles.add(full_url)
                            print('\r', f"Count: [{len(articles)} of {max_url}]", end='', flush=True)
            else:
                print(f"Failed to fetch {current_url}. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error fetching {current_url}: {e}")
    if output_path:
        dir_path, filename = os.path.split(output_path)
        with open(os.path.join(dir_path, "ARTC_" + filename), 'w') as file:
            # Iterate through the list of URLs
            for url in articles:
                # Write each URL to the file followed by a newline character
                file.write(url + '\n')
        with open(os.path.join(dir_path, "ALL_" + filename), 'w') as file:
            # Iterate through the list of URLs
            for url in visited_urls:
                # Write each URL to the file followed by a newline character
                file.write(url + '\n')
    
    return articles, visited_urls
   
def jina_reader(url, uid, save=False, output=None):
    """
        The response from JINA has the following structure:
        {
            satus: 200
            "data": {
                "title": The title of the article,
                "url": URL of the article
                "content": The article text
                "publishedTime": The publiseh time in '2024-06-17T10:34:05+00:00' format
            }        
        }

    """
    jina = 'https://r.jina.ai/'
    headers = {
    "Authorization": MACHINE_CONFIG.JINA_KEY,
    "Accept": "application/json"
    }
    print("\tRead with Jina >> ", end="")
    response = requests.get(jina+url, headers=headers)
    response_text = response.text
    # Checking the status of the request
    if response.status_code == 200:
        response_body = response.content.decode('utf-8')
        response_body = json.loads(response_body)["data"]
        title = response_body["title"].strip().replace(" ", "_")
        text = response_body["content"]
    else:
        print(f'Failed to fetch data. Status code: {response.status_code}')
    if save:
        if  output is None: 
            output=str(str(uid)+".md")
        with open(os.path.join(output, str(uid)+".md"), "w", encoding="utf-8") as file:
            file.write(text)
        print("Saved >> ", end="")
    print("Finished!")
    return response_body
    
def find_images_in_md_text(text):
    """
    # Function to find all image links in a Markdown file
    """
    image_pattern = r'!\[(.*?)\]\((.*?)\)'
    matches = re.findall(image_pattern, text)

    return matches

def find_images_on_page(url):
    article = newspaper.Article(url)
    article.download()
    article.parse()
    return article.images

def extrat_metadata(url, client:Groq=None, verbal=False):
    """
    {
    "author":  ["author name"], 
    "tags": [ "list of tags" ],
    "category": [ "list of categories" ]
    }
    """
    print(f"\tExtrat metadata >> ", end="")
    response = requests.get(url)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()

    all_text = soup.get_text(separator=' ', strip=True)

    link_texts = "\n".join([link.get_text(strip=True) for link in soup.find_all('a') ])

    final_content = f"The page text: \n\n {all_text}\n\nAll link text in page: \n\n {link_texts}"
    for i in range(MACHINE_CONFIG.TRY_OUT):
        try: 
            if client is None:
                client = Groq(
                    api_key=MACHINE_CONFIG.GROQ_KEY,
                )
            chat_completion = client.chat.completions.create(
                response_format = {"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": scraper_prompts.SYS_METADATA,
                    },
                            {
                        "role": "user",
                        "content": final_content,
                    }
                ],
                model=MACHINE_CONFIG.MODELL_META
            )
            respond = chat_completion.choices[0].message.content
            if verbal: print(f"\n\tThe respond: \n{respond}")
            loaded_data = json.loads(respond)
            print("Finished")
            return loaded_data
        except Exception as e:
            print(f"\n\tThere was an error generating the metadata: {e} \n\tIteration [{i+1} of {MACHINE_CONFIG.TRY_OUT}]")

def create_summary(text, client:Groq=None, verbal=False):
    print("\tCreate summary >> ", end="")
    summary = None
    headline = None
    if client is None:
        client = Groq(
            api_key=MACHINE_CONFIG.GROQ_KEY,
        )
    for i in range(MACHINE_CONFIG.TRY_OUT):
        try: 
            if summary is None:
                summary = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": scraper_prompts.SYS_SUMMARY,
                        },
                                {
                            "role": "user",
                            "content": text,
                        }
                    ],
                    model=MACHINE_CONFIG.MODELL_SUMMARY,
                ).choices[0].message.content
            if headline is None:
                headline = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": scraper_prompts.SYS_HEADLINE,
                        },
                                {
                            "role": "user",
                            "content": text,
                        }
                    ],
                    model=MACHINE_CONFIG.MODELL_HEADLINE,
                ).choices[0].message.content
            if verbal: print(f"\n\tHeadLine: {headline}\n\tSummary: {summary}")
            print("Finished!")
            if summary != None and headline != None:
                return summary, headline
        except Exception as e:
            print(f"\tThere was an error generating the Summary: {e} \n\tIteration [{i+1} of {MACHINE_CONFIG.TRY_OUT}]")
            return None, None

def construct_article(url, uid, client:Groq=None, save=False, output=None):
    print(f"Construct: {url}")
    #----------------------------------------------------------------
    # Formated text
    data = jina_reader(url=url, uid=uid, save=save, output=output)
    #----------------------------------------------------------------
    # Images
    images = find_images_in_md_text(data["content"])
    if len(images) == 0:
        images = find_images_on_page(url)
    #----------------------------------------------------------------
    # Metadata and sentiment
    sentiment = None
    metadata = extrat_metadata(url, client=client, verbal=False)
    #----------------------------------------------------------------
    # Summary and keywords
    summary, one_liner = create_summary(data["content"], client, False)
    keywords = None

    article = {
        "uid": str(uid),
        "url": url,
        "full_text": data["content"],
        "summary": summary,
        "one_liner": one_liner,
        "sentiment": sentiment,
        "keywords": keywords,
        "images": images,
        "title": data["title"],
        "time_stamp": data["publishedTime"],
        "authors": metadata["author"],
        "tags": metadata["tags"],
        "category": metadata["category"]
    }
    if save:
        try:
            if  output is None: 
                output=str(str(uid)+".json")
            with open(os.path.join(output, str(str(uid)+".json")), "w", encoding="utf-8") as file:
                json.dump(article, file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"There was an Error constructing the JSON output writing it to txt.")
            with open(os.path.join(output, str(str(uid)+".json")), "w", encoding="utf-8") as file:
                for key, value in article.items():
                    file.write(f'{key}: {value}\n')
    return article

def site_selector(config_path):
    print("-"*60, "\nSCRAPER v0.1\n" "The following sites are available:")
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    site_index_array = []
    for index, key in enumerate(config, start=0):
        if index==0: continue
        print(f"\t - [{index}] >> {config[key]['url']}")
        site_index_array.append(key)
    site_key = site_index_array[int(input(f"Select a site [1-{len(site_index_array)}]: "))-1]
    site_config = config[site_key]
    site_url = site_config['url']
    headers = config["headers"]
    site_config["headers"] = headers
    print("-"*60, f"\nYou choose to scrape: {site_url} >>")
    for key in site_config:
        print(f"\t[{key}] : {site_config[key]}")
    count = int(input("\nGive me the maximum amount of pages that you want to get: "))
    
    output = os.path.join("data", (site_key+".txt"))
    print(f"The Files wil be saved to >> {output} \n\nExtracting:>>\n")
    articles, visited = get_articles(site_config, count, output, verbal=False)
    print(f"\n Viseted: [{len(visited)}]", f"\n Extracted: [{len(articles)}]")


class Scraper:
    def __init__(self, config_path, global_verbal=False):
        self.config_path = config_path
        self.global_verbal = global_verbal
        with open(config_path, "r", encoding="utf-8") as config_file:
            self.config = json.load(config_file)
        
        self.client = Groq(
                api_key=MACHINE_CONFIG.GROQ_KEY,
            )

    def site_selector(self):
        self.site_index_array = []
        for index, key in enumerate(self.config, start=0):
            if index==0: continue
            print(f"\t - [{index}] >> {self.config[key]['url']}")
            self.site_index_array.append(key)
        site_key = self.site_index_array[int(input(f"Select a site [1-{len(self.site_index_array)}]: "))-1]
        site_config = self.config[site_key]
        site_config["headers"] = self.config["headers"]
        print("-"*60, f"\nYou choose to scrape: {site_config['url']} >>")
        for key in site_config:
            print(f"\t[{key}] : {site_config[key]}")
        count = int(input("\nGive me the maximum amount of pages that you want to get: "))
        return {"site_key": site_key, "count": count}
    
    def get_site_articles(self, key, count, path="data", verbal=False):
        if verbal: print(f"The Files wil be saved to >> {output} \n\nExtracting:>>\n")
        output = os.path.join(path, (key+".txt"))
        try: 
            site_config = self.config[key]
            site_config["headers"] = self.config["headers"]

            articles, visited = get_articles(site_config, count, output, verbal=self.global_verbal)
            if verbal: print(f"\n Viseted: [{len(visited)}]", f"\n Extracted: [{len(articles)}]")
            return articles
        except Exception as e:
            print(e)
            return None

    def collect_site(self, urls, output):
        os.makedirs(output, exist_ok=True)
        for url in urls:
            url_uid1 = uuid.uuid1()
            construct_article(url, url_uid1, self.client, True, output)

    def collect_all(self, count, root="scraper_output"):
        root = os.path.join(root, "scraper_output")
        for key in self.config:
            if key=="headers": continue
            output_dir = os.path.join(root, key)
            os.makedirs(output_dir, exist_ok=True)
            print("-"*60, f"\nCollecting {key}:")
            urls = self.get_site_articles(key, count, output_dir)
            self.collect_site(urls, output_dir)
    
if __name__ == "__main__":
    scraper = Scraper(CONFIG_PATH)
    urls_path = r"C:\Users\andra\OneDrive\Dokumentumok\Munka\WeSpeakAi\GoodPeople\data\ARTC_monitorblog.txt"
    output = r"C:\Users\andra\OneDrive\Dokumentumok\Munka\WeSpeakAi\GoodPeople\data\mbh"
    with open(urls_path, "r") as file:
        urls = file.readlines()

    scraper.collect_site(urls=urls[:10], output=output)