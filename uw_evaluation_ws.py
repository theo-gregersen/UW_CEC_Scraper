from requests import get, Request, Session
import requests
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
import time
import os
import pandas as pd
import matplotlib.pyplot as plt

cur_session = None
working_data = pd.DataFrame()
stored_data = {}
courses_scanned = 0
courses_saved = 0

# represents a uw course
class course():

    def __init__(self, title, teacher, quarter, table, series, medians):
        self.title = title
        self.teacher = teacher
        self.quarter = quarter
        self.table = table
        self.series = series
        self.medians = medians
        self.cid = str(title + ' ' + teacher + ' ' + quarter) # not working properly?
        self.medians['ID'] = self.cid
        self.series['ID'] = self.cid

# returns html content from provided url
def get_content(url):
    try: # attempts an http request
        with closing(cur_session.get(url, timeout = 3)) as response:
            if is_good_request(response):
                return response.content
            else:
                raise Exception('HTTP Status Error: {0}'.format(response.status_code))
                return None
    except RequestException as e:
        log_error('Error during request to {0} : {1}'.format(url, str(e)))
        return None
        
# accepts a request object, returns a boolean representing if the request object was successful and contains usable html
def is_good_request(response):
    content_type = response.headers['content-type'] # finds page content type from http header info
    return (response.status_code == 200 and # http code 200 indicates successful request
        content_type is not None and 
        content_type.find('html') > -1)

# uses selenium to handle shibboleth authentication, stores auth cookies to the program request session
def authentication_input(usern, passw):
    os.system('cls')
    print('authenticating. . .')
    options = Options()
    options.add_argument('--headless') # hides firefox window
    driver = webdriver.Firefox(options=options)
    driver.get('https://www.washington.edu/cec/toc.html')
    try:
        login_load = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'weblogin_netid')))
    except:
        raise Exception('Login time out')
    driver.find_element_by_id('weblogin_netid').send_keys(usern)
    driver.find_element_by_id('weblogin_password').send_keys(passw)
    driver.find_element_by_id('submit_button').click()
    try:
        cookie_load = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'toolbar')))
    except:
        raise Exception('Login failed')
    global cur_session
    cur_session = requests.Session()
    cur_cookies = driver.get_cookies()
    for cookie in cur_cookies: # transfering selenium cookie data into request session to preserve auth
        cur_session.cookies.set(cookie['name'], cookie['value'])
    driver.close()

# returns a pandas dataframe representing the course's data table
def parse_for_df(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    if formatted_html.find('table') is not None:
        headers = list() 
        for h in formatted_html.find_all('th'):
            headers.append(h.get_text())
        df = pd.DataFrame(columns = headers)
        class_table = formatted_html.find('table')
        rows = class_table.find_all('tr')
        for row in rows:
            stats = list()
            for col in row.find_all('td'):
                str = col.get_text().replace('%','',1).strip() # allowing %'s to be used in pandas
                try:
                    fl = float(str)
                    stats.append(fl)
                except:
                    stats.append(str)
            if len(stats) > 0:
                df = df.append(pd.Series(stats, index=df.columns), ignore_index=True) # appending a row to the df
        return df
    else:
        return None

# returns a dictionary representing the course's data table (keys are column indexes for adding to df)
def parse_for_series(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    questions = ['CW','CC','IC','IE','II','AL','GT']
    itrq = -1 # start at -1 to handle the initial header row
    rating = ['E','VG','G','F','P','VP','M']
    itrr = 0
    if formatted_html.find('table') is not None:
        stats = {}
        class_table = formatted_html.find('table')
        rows = class_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            for col in cols:
                str = col.get_text().replace('%','',1).strip()
                if str[0].isdigit():
                    key = questions[itrq] + rating[itrr]
                    itrr += 1
                    try:
                        fl = float(str)
                        stats[key] = fl
                    except:
                        stats[key] = str
            itrq += 1
            itrr = 0
        return stats
    else:
        return None

# returns a dictionary representing the course median data (keys are column indexes for adding to df)
def parse_for_medians(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    headers = ['CW','CC','IC','IE','II','AL','GT']
    if formatted_html.find('table') is not None:
        medians = list()
        median_dictionary = {}
        class_table = formatted_html.find('table')
        rows = class_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            for col in cols:
                str = col.get_text().strip()
                if '.' in str and str.replace('.','',1).isdigit():
                    try:
                        fl = float(str)
                        medians.append(fl)
                    except:
                        medians.append(str)
        for x in range(len(headers)):
            median_dictionary[headers[x]] = medians[x]
        return median_dictionary
    else:
        return None

# returns course title from url
def parse_title(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    if formatted_html.find('h1') is not None:
        return formatted_html.find('h1').get_text()
    else:
        return 'missing title'

# returns course quarter
def parse_quarter(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    if formatted_html.find('h2') is not None:
        h2 = formatted_html.find('h2').get_text()
        return h2[len(h2)-4:]
    else:
        return 'missing quarter'

# returns teacher name
def parse_teacher(url):
    raw_html = get_content(url)
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    if formatted_html.find('h2') is not None:
        contents = formatted_html.find('h2').get_text().split()
        str = ''
        itr = 0
        types = ['Lecturer', 'Instructor', 'Pre-Doctoral', 'Assistant', 'Associate', 'Other', 'Teaching', 'Professor']
        while itr < len(contents) and contents[itr].strip() not in types:
            str = str + ' ' + contents[itr]
            itr = itr + 1
        return str.strip()
    else:
        return 'missing teacher'

# returns a course object with parsed information
def scrape_course(url):
    title = parse_title(url)
    teacher = parse_teacher(url)
    quarter = parse_quarter(url)
    table = parse_for_df(url)
    series = parse_for_series(url)
    medians = parse_for_medians(url)
    return course(title, teacher, quarter, table, series, medians)

# scrapes cec and adds courses containing search term (case sensitive) to stored data
def scrape_by_type(term):
    raw_html = get_content('https://www.washington.edu/cec/toc.html')
    toc_html = BeautifulSoup(raw_html, 'html.parser')
    for href in toc_html.find_all('a', href=True):
        if len(href.get_text()) == 1:
            url = 'https://www.washington.edu/cec/' + href.get('href')
            scrape_by_type_helper(term, url)

# scrapes cec content for the given letter, adds courses containing search term (case sensitive) to stored data
def scrape_by_type_restrict(term, letter):
    raw_html = get_content('https://www.washington.edu/cec/toc.html')
    toc_html = BeautifulSoup(raw_html, 'html.parser')
    url = 'https://www.washington.edu/cec/' + letter.lower() + '-toc.html'
    scrape_by_type_helper(term, url)

# recursively follows links with label containing search term, if url contains course data and term, adds the course to stored data
# warning: potential for infinite loop if the search term appears in circular menu links
def scrape_by_type_helper(term, url):
    global courses_saved
    global courses_scanned
    raw_html = get_content(url)  
    formatted_html = BeautifulSoup(raw_html, 'html.parser')
    for href in formatted_html.find_all('a', href=True):
        courses_scanned += 1
        if term in href.get_text():
            sub_url = 'https://www.washington.edu/cec/' + href.get('href')
            scrape_by_type_helper(term, sub_url)
    h1 = formatted_html.find('h1')
    h2 = formatted_html.find('h2')
    if h1 is not None and h2 is not None and (term in h1.get_text() or term in h2.get_text()):
        courses_saved += 1
        course = scrape_course(url)
        stored_data[course.cid] = course
    update_scr_scraping()

# scrapes the entire cec, adding all courses to stored data
def full_scrape():
    scrape_by_type('')

# updates console screen during scraping
def update_scr_scraping():
    os.system('cls')
    global courses_scanned
    global courses_saved
    print('courses scanned: {0} courses saved: {1}'.format(courses_scanned, courses_saved))

# sets working data type to handle series (full data)
def set_wdtype_full():
    global working_data
    headers = ['ID']
    questions = ['CW','CC','IC','IE','II','AL','GT']
    ratings = ['E','VG','G','F','P','VP','M']
    for q in questions:
        for r in ratings:
            headers.append(q + r)
    working_data = pd.DataFrame(columns=headers)

# sets up working dataframe for median analysis
def set_wdtype_medians():
    global working_data
    headers = ['ID','CW','CC','IC','IE','II','AL','GT']
    working_data = pd.DataFrame(columns=headers)

# adds all the series from stored data to working data
def wd_fill_full():
    global stored_data
    global working_data
    for course in stored_data:
        working_data = working_data.append(stored_data[course].series, ignore_index=True)

# adds all the median series from stored data to working data
def wd_fill_medians():
    global stored_data
    global working_data
    for course in stored_data:
        working_data = working_data.append(stored_data[course].medians, ignore_index=True)

# sorts the working data based on provided column(s) and if user wants to sort in ascending order
def sort_wd(column, ascending):
    global working_data
    if column in working_data.columns:
        working_data.sort_values(column, ascending=ascending, inplace=True)
    else:
       print('Invalid column') 

# creates a matplotlib graph of given type using selected columns for x and y arguments
def print_wd_graph(graph_type, x_args, y_args):
    global working_data
    if x_args in working_data.columns and y_args in working_data.columns:
        working_data.plot(kind=graph_type, x=x_args, y=y_args, color='blue')
        plt.show()
    else:
        print('Invalid column(s)')

# prints error
def log_error(e):
    print(e)

# call methods here
def main():
    pd.options.display.max_columns = 55
    authentication_input(input('netid: '), input('password: '))
    scrape_by_type_restrict('Asian American','a')
    set_wdtype_medians()
    wd_fill_medians()
    sort_wd('CW', False)
    print(working_data)
    print_wd_graph('bar','ID','CW')


# run main method on start
if __name__ == '__main__':
    main()

