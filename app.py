#For Github

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import os
import time
import sys
from datetime import datetime
import shutil
import glob
import requests
import json
import time
import pandas as pd
from datetime import datetime, timedelta
import dateutil.parser

#! Important Variables
API_KEY = '<API KEY>'
domain_id = '<ID>'
HEADERS = {'Authorization': f'Bearer {API_KEY}'}
REQUEST_POLL = f'https://<ENDPOINT>/rest/monitor_poll/v2?not_modified_since=1970-01-01T00%3A00%3A0&domain_id={domain_id}'
QUERY_BY_ID = 'https://<ENDPOINT>/rest/host/v17/'
GMAIL_PW = '<APP PASSWORD>'
#! System Variables
reports_path = '/path/to/reports'
path = '/path/to/dir'
timestr = time.strftime('[%Y-%m-%d]')
today = time.strftime('%Y-%m-%d')
folder_exist = f'{path}{today}'
poll = []
host = []

#search for file based on 'last_week' 
last_week_search = glob.glob(
    f'{reports_path}/last_week*') 
#search for file based on 'current_week' 
current_week_search = glob.glob(
    f'{reports_path}/current_week*')

def request(endpoint):
    r = requests.get(
        url= endpoint, headers=HEADERS) #request json 
    r = r.json()
    return r
def get_status():
    res = request(REQUEST_POLL)
    
    for value in res['monitor_poll']:
    #need to loop through json file to see if a unit is active 1 = Online 2 = Registered, but not connected
        if value['monitor_status'] == 1 or value['monitor_status'] == 2: 
    #append to a list       
            poll.append(value) 
    #needed to run in pandas
    jsonData = json.dumps(poll) 
    # open in pandas
    df1 = pd.read_json(jsonData)
    #drop these col headers
    df1 = df1.drop(['domain_id', 'id', 'poll_next_expected_utc',
                    'private_ip', 'product_version', 'public_ip'], axis=1) 
    #change 1 to online and 2 of Missing in Action
    df1['monitor_status'].replace(
        {1: 'Online', 2: 'Missing in Action'}, inplace=True) 
    #change UTC to Month/Date/Year, I don't know how to convert UTC to days, mins, hours
    df1['poll_last_utc'] = pd.to_datetime(
    df1['poll_last_utc']).dt.strftime('%m-%d-%Y') 
    #col renames
    df1.rename(columns={'client_resource_id': 'id', 'monitor_status': 'status',
                    'poll_last_utc': 'last_online'}, inplace=True) 
    #will pd.merge on 'id'
    get_name(df1)
get_status()

#Since the first report doesn't give the name of the location I have to hit another endpoint to get the name and merge on ID with name
def get_name(csv):
    res = request(QUERY_BY_ID)
    
    #loop through to find what is active or not
    for value in res['host']: 
        if value['active'] == True:
            host.append(value)
    jData = json.dumps(host)
    df2 = pd.read_json(jData)
    #drop cols
    df2 = df2.drop(['active', 'config_profile_bag_id', 'container_id', 'custom_unique_id', 'db_pickup_tm_utc', 'discovery_status', 'display_unit_id', 'domain_id',
                    'geolocation', 'nscreens', 'primary_mac_address', 'public_key_fingerprint', 'remote_clear_db_tm_utc', 'remote_reboot_tm_utc',
                    'secondary_mac_address', 'volume'], axis=1) 
    #need to "Fixed Width" example of the name UTV0001 XYZ Store
    new = df2['name'].str.split(" ", n = 1, expand=True) 
    #stores TV Number
    df2['TV Number'] = new[0]
    #store Store Name 
    df2['Store Name'] = new[1] 
    #drop col
    df2.drop(columns=['name'], inplace=True) 
    #merging both DF's on id 
    df2 = pd.merge(df2, csv, on=['id']) 
    #drop col
    df2 = df2.drop(['id'], axis=1)
    #call next func
    merge_on_main(df2) 

#Merge on main take DF from get_name and merge on main CSV which houses all units regardless if it's online, missing, or inactive
def merge_on_main(csv): 
    df3 = pd.read_csv(
        f'{reports_path}/SO_Listing.csv') #main CSV 
    df3.rename(columns={'UltraTV#': 'TV Number', }, inplace=True)
    #example col TV Number	Customer	RetailerID	Current Week	last_online
    #can't merge on retailer id because ENDPOINTS do not have that info since it is internal
    df4 = pd.merge(df3, csv, on=['TV Number'], how='outer') 
    #col drop 
    df4.drop(columns=['Store Name'], inplace=True) 
    #fill in empty space with 'Inactive' means not tied into CMS
    df4['status'].fillna('Inactive', inplace=True) 
    df4.rename(columns={'status': 'Current Week', }, inplace=True)
    df4['last_online'].fillna('Inactive', inplace=True)
    #report for this week
    df4.to_csv(
        f'{path}/current_week{timestr}.csv', index=False) 
    #Gives time to write CSV
    time.sleep(2) 
    file_move()
    
   #check if folder exists 
def check_folder(last_week_file, current_week_file, new_folder, reports_path):
        # #find newest last_week.csv file based on modified time
        # last_week_file = max(last_week_search, key=os.path.getmtime) 
        # #find newest current_week.csv file based on modified time
        # current_week_file = max(current_week_search, key=os.path.getmtime)
        # #finds newest folder if already made
        # new_folder = max(glob.glob(os.path.join(path, '*/')),
        #                  key=os.path.getmtime) 
        #copy current week to new folder 
        shutil.copy2(f'{current_week_file}', f'{new_folder}') 
        #moves last week file..no longer needed after today
        shutil.move(f'{last_week_file}', f'{new_folder}/')  
        #takes current week and rename it to next week for next week report
        shutil.move(f'{current_week_file}', f'{reports_path}/last_week-from-{timestr}.csv') 
        #cd into new folder
        os.chdir(new_folder) 
        report_completion()
        
   #if no folder exists run this     
def no_folder():
        print(f'Folder does not exist! Making folder: {today}')
        #make dir based on today's date and make it R/W
        make_folder = os.mkdir(path + time.strftime('%Y-%m-%d'), mode=0o777) 
        check_folder(max(last_week_search, key=os.path.getmtime), max(current_week_search, key=os.path.getmtime), max(glob.glob(os.path.join(path, '*/')),
                         key=os.path.getmtime), reports_path = 'path/to/reports')
    
#File Navigation
def file_move():
    #Does folder Exist?
    if os.path.exists(folder_exist):
        check_folder(max(last_week_search, key=os.path.getmtime), max(current_week_search, key=os.path.getmtime), max(glob.glob(os.path.join(path, '*/')),
                         key=os.path.getmtime), reports_path = 'path/to/reports')
    else: #this usually runs first since we haven't made a folder, if just for checks and usually testing
        no_folder()

def report_completion():
    #still in same dir
    filename = os.listdir()
    files_in_dir = [f for f in filename if f.endswith('.csv')]
    
    #find the files again
    for f in files_in_dir:
        if f.endswith('csv'):
            if f.startswith('current'):
                df1 = pd.read_csv(f)

            if f.startswith('last'):
                df2 = pd.read_csv(f)

    #Need to figure out how to do merges better
    df3 = pd.merge(df1, df2, on=['TV Number',
                                 'Customer', 'RetailerID'], how='outer') 
    
    #final merge cols TV Number	Customer RetailerID	Current Week Last Online Last Week
    df3.drop(columns=['last_online_y'], inplace=True)
    df3.rename(columns={'last_online_x': 'Last Online','Current Week_x':'Current Week', 'Current Week_y': 'Last Week'}, inplace=True)
    report = df3.to_csv(f'{today}.csv', index=False)
    print('Report Completed, sending Email')
    send_email()


def send_email():
    my_email = "from@test.com"
    to = "test@test.com"
    msg = MIMEMultipart() 
    msg['From'] = my_email
    msg['To'] = to
    msg['Subject'] = f"Report {today}"
    body = """
    Someone,
    
    Here is today's report
    
    -sent from python
    """
    msg.attach(MIMEText(body, 'plain'))
    filename = os.listdir() 
    #file to be sent
    files_in_dir = [f for f in filename if f.endswith('.csv')]
    #find final csv starts with 2020/M/Day
    for f in files_in_dir:
        if f.endswith('csv'):
            if f.startswith('2020-'): 
                filename = f
    attachment = open(f'{folder_exist}/{filename}', "rb")
    p = MIMEBase('application', 'octet-stream')
    p.set_payload((attachment).read())
    encoders.encode_base64(p)
    p.add_header('Content-Disposition', "attachment; filename= %s" % filename)
    msg.attach(p)
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(my_email, f'{GMAIL_PW}')
    text = msg.as_string()
    s.sendmail(my_email, to, text)
    print(f'Email sent to: {to}')
    s.quit()



