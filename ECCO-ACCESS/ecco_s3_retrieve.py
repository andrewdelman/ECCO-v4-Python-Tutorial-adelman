### This module contains routines to access and retrieve ECCO datasets on the AWS Cloud.
### These functions will only work when called from an AWS EC2 instance running in region us-west-2.


## Initalize Python libraries for module
import numpy as np
import pandas as pd
import requests
import time as time
import os.path
from os.path import basename, isfile, isdir, join, expanduser
from pathlib import Path


def ecco_podaac_s3_query(ShortName,StartDate,EndDate):
    
    """
    
    This routine searches for files of the given ShortName and date range.
    It returns a list of files that can be opened or downloaded to a user's local instance.
    This function is called by the other routines in this module.
    
    Parameters
    ----------
    ShortName: str, the ShortName that identifies the dataset on PO.DAAC.
    
    StartDate,EndDate: str, in 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' format, 
                       define date range [StartDate,EndDate] for download.
                       EndDate is included in the time range (unlike typical Python ranges).
                       ECCOv4r4 date range is '1992-01-01' to '2017-12-31'.
                       For 'SNAPSHOT' datasets, an additional day is added to EndDate to enable closed budgets
                       within the specified date range.

    Returns
    -------
    s3_files_list: str or list, opened file(s) on S3 that can be passed directly to xarray 
                   (open_dataset or open_mfdataset)
    
    """

    pass

    ## Initalize Python libraries
    from platform import system
    from netrc import netrc
    from os.path import basename, isfile, isdir, join, expanduser
    from urllib import request
    from http.cookiejar import CookieJar
    

    # Predict the path of the netrc file depending on os/platform type.
    _netrc = join(expanduser('~'), "_netrc" if system()=="Windows" else ".netrc")
    

    ## Define Helper Subroutines
    
    ### Helper subroutine to log into NASA EarthData
    
    # not pretty but it works
    def setup_earthdata_login_auth(url: str='urs.earthdata.nasa.gov'):
        # look for the netrc file and use the login/password
        try:
            username, _, password = netrc(file=_netrc).authenticators(url)
    
        # if the file is not found, prompt the user for the login/password
        except (FileNotFoundError, TypeError):
            print('Please provide Earthdata Login credentials for access.')
            username, password = input('Username: '), getpass('Password: ')
        
        manager = request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, url, username, password)
        auth = request.HTTPBasicAuthHandler(manager)
        jar = CookieJar()
        processor = request.HTTPCookieProcessor(jar)
        opener = request.build_opener(auth, processor)
        request.install_opener(opener)
    
    ### Helper subroutines to make the API calls to search CMR and parse response
    def set_params(params: dict):
        params.update({'scroll': "true", 'page_size': 2000})
        return {par: val for par, val in params.items() if val is not None}
    
    def get_results(params: dict, headers: dict=None):
        response = requests.get(url="https://cmr.earthdata.nasa.gov/search/granules.json", 
                                params=set_params(params),
                                headers=headers).json()
        return response    
    
    def get_granules(params: dict):
        response = get_results(params=params)
        if 'feed' in response.keys():
            s3_files_list = []
            for curr_entry in response['feed']['entry']:
                for curr_link in curr_entry['links']:
                    if "direct download access via S3" in curr_link['title']:
                        s3_files_list.append(curr_link['href'])
                        break
        elif 'errors' in response.keys():
            raise Exception(response['errors'][0])

        return s3_files_list    
    

    # # Adjust StartDate and EndDate to CMR query values
    
    if StartDate=='yesterday':
        StartDate = yesterday()
    if EndDate==-1:
        EndDate = StartDate
    elif StartDate=='yesterday':
        StartDate = yesterday()
    elif EndDate=='today':
        EndDate = today()
    
    if len(StartDate) == 4:
        StartDate += '-01-01'
    elif len(StartDate) == 7:
        StartDate += '-01'
    elif len(StartDate) != 10:
        sys.exit('\nStart date should be in format ''YYYY'', ''YYYY-MM'', or ''YYYY-MM-DD''!\n'\
                 +'Program will exit now !\n')
    
    if len(EndDate) == 4:
        EndDate += '-12-31'
    elif len(EndDate) == 7:
        EndDate = str(np.datetime64(str(np.datetime64(EndDate,'M')+np.timedelta64(1,'M'))+'-01','D')\
                      -np.timedelta64(1,'D'))
    elif len(EndDate) != 10:
        sys.exit('\nEnd date should be in format ''YYYY'', ''YYYY-MM'', or ''YYYY-MM-DD''!\n'\
                 +'Program will exit now !\n')
    
    
    # for monthly and daily datasets, do not include the month or day before
    if (('MONTHLY' in ShortName) or ('DAILY' in ShortName)):
        if np.datetime64(EndDate,'D') - np.datetime64(StartDate,'D') \
          > np.timedelta64(1,'D'):
            StartDate = str(np.datetime64(StartDate,'D') + np.timedelta64(1,'D'))
            SingleDay_flag = False
        else:
            # for single day ranges we need to make the adjustment
            # after the CMR request
            SingleDay_flag = True
    # for snapshot datasets, move EndDate one day later
    if 'SNAPSHOT' in ShortName:
        EndDate = str(np.datetime64(EndDate,'D') + np.timedelta64(1,'D'))

    
    ## Log into Earthdata using your username and password
    
    # actually log in with this command:
    setup_earthdata_login_auth()
    
    # Query the NASA Common Metadata Repository to find the URL of every granule associated with the desired 
    # ECCO Dataset and date range of interest.
    
    # create a Python dictionary with our search criteria:  `ShortName` and `temporal`
    input_search_params = {'ShortName': ShortName,
                           'temporal': ",".join([StartDate, EndDate])}
    
    print(input_search_params)
    
    ### Query CMR for the desired ECCO Dataset
    
    # grans means 'granules', PO.DAAC's term for individual files in a dataset
    s3_files_list = get_granules(input_search_params)

    return s3_files_list



###================================================================================================================


def init_S3FileSystem():
    
    """
    
    This routine automatically pulls your EDL crediential from .netrc file and use it to obtain an AWS S3 credential 
    through a PO.DAAC service accessible at https://archive.podaac.earthdata.nasa.gov/s3credentials.
    From the PO.DAAC Github (https://podaac.github.io/tutorials/external/July_2022_Earthdata_Webinar.html).
    
    Returns:
    =======        
    s3: an AWS S3 filesystem
    
    """
    
    import requests
    import s3fs
    
    creds = requests.get('https://archive.podaac.earthdata.nasa.gov/s3credentials').json()
    s3 = s3fs.S3FileSystem(anon=False,
                           key=creds['accessKeyId'],
                           secret=creds['secretAccessKey'], 
                           token=creds['sessionToken'])
    
    return s3



###================================================================================================================


def download_file(s3, url, output_dir, force):
    
    """
    Helper subroutine to gracefully download single files and avoids re-downloading if file already exists.
    To force redownload of the file, pass **True** to the boolean argument *force* (default **False**).

    Parameters
    ----------
    url: str, the HTTPS url from which the file will download
    output_dir: str, the local path into which the file will download
    force: bool, download even if the file exists locally already

    Returns
    -------
    target_file: str, downloaded file path
    
    """

    pass
    
    if not isdir(output_dir):
        raise Exception(f"Output directory doesn't exist! ({output_dir})")
    
    target_file = join(output_dir, basename(url))
    
    # if the file has already been downloaded, skip    
    if isfile(target_file) and force is False:
        print(f'\n{basename(url)} already exists, and force=False, not re-downloading')
        return target_file

    # download file to local (output) file directory
    s3.get_file(url, target_file)

    return target_file



###================================================================================================================


def download_files_concurrently(s3, dls, download_dir, n_workers, force=False):
    """Download files using thread pool with up to n_workers"""

    pass
    
    start_time = time.time()

    # use thread pool for concurrent downloads
    with ThreadPoolExecutor(max_workers=n_workers) as executor:

        # tqdm makes a cool progress bar
        downloaded_files = list(tqdm(executor.map(download_file, repeat(s3), dls, repeat(download_dir), repeat(force)),\
                                     total=len(dls), desc='DL Progress',\
                                     ascii=True, ncols=75, file=sys.stdout))
    
        # calculate total time spent in the download
        total_time_download = time.time() - start_time

        print('\n=====================================')
        print('Time spent = ' + str(total_time_download) + ' seconds')
        print('\n')

    return downloaded_files



###================================================================================================================


def download_files_wrapper(s3, s3_files_list, download_dir, n_workers, force_redownload):
    """Wrapper for downloading functions"""

    pass
    
    try:
        # Attempt concurrent downloads, but if error arises switch to sequential downloads
        ### Method 1: Concurrent downloads        
        
        # Force redownload (or not) depending on value of force_redownload
        downloaded_files = download_files_concurrently(s3, s3_files_list, download_dir, n_workers, force_redownload)
        
    except:
        ### Method 2: Sequential Downloads
        
        start_time = time.time()
        
        # Download each URL sequentially in a for loop.
        total_download_size_in_bytes = 0
        
        # loop through all files
        downloaded_files = []
        for u in s3_files_list:
            u_name = u.split('/')[-1]
            print(f'downloading {u_name}')
            result = download_file(s3, url=u, output_dir=download_dir, force=force_redownload)
            downloaded_files.append(result)
        
        # calculate total time spent in the download
        total_time_download = time.time() - start_time
        
        print('\n=====================================')
        print('Time spent = ' + str(total_time_download) + ' seconds')
        print('\n')

        return downloaded_files



###================================================================================================================


def ecco_podaac_s3_open(ShortName,StartDate,EndDate):
    
    """
    
    This routine searches for and opens ECCO datasets from S3 buckets in the PO.DAAC Cloud.
    It returns a list of opened file(s) on S3 that can be passed to xarray.
    This function is intended to be called from an EC2 instance running in AWS region us-west-2.
    
    Parameters
    ----------
    ShortName: str, the ShortName that identifies the dataset on PO.DAAC.
    
    StartDate,EndDate: str, in 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' format, 
                       define date range [StartDate,EndDate] for download.
                       EndDate is included in the time range (unlike typical Python ranges).
                       ECCOv4r4 date range is '1992-01-01' to '2017-12-31'.
                       For 'SNAPSHOT' datasets, an additional day is added to EndDate to enable closed budgets
                       within the specified date range.

    Returns
    -------
    open_files: str or list, opened file(s) on S3 that can be passed directly to xarray (open_dataset or open_mfdataset)
    
    """

    pass    
        
    # get list of files
    s3_files_list = ecco_podaac_s3_query(ShortName,StartDate,EndDate)

    num_grans = len(s3_files_list)
    print (f'\nTotal number of matching granules: {num_grans}')

    # initiate S3 access
    s3 = init_S3FileSystem()
    # open files and create list that can be passed to xarray file opener
    open_files = [s3.open(file) for file in s3_files_list]
    # if list has length 1, return a string instead of a list
    if len(open_files) == 1:
        open_files = open_files[0]

    return open_files



###================================================================================================================


def ecco_podaac_s3_get(ShortName,StartDate,EndDate,download_root_dir=None,n_workers=6,\
                       force_redownload=False,return_downloaded_files=False):

    """
    
    This routine downloads ECCO datasets from PO.DAAC, to be stored locally on a AWS EC2 instance running in 
    region us-west-2. It is adapted from the ecco_podaac_download function in the ecco_download.py module, 
    and is the AWS Cloud equivalent of ecco_podaac_download.
    
    Parameters
    ----------
    
    ShortName: str, the ShortName that identifies the dataset on PO.DAAC.
    
    StartDate,EndDate: str, in 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' format, 
                       define date range [StartDate,EndDate] for download.
                       EndDate is included in the time range (unlike typical Python ranges).
                       ECCOv4r4 date range is '1992-01-01' to '2017-12-31'.
                       For 'SNAPSHOT' datasets, an additional day is added to EndDate to enable closed budgets
                       within the specified date range.
    
    download_root_dir: str, defines parent directory to download files to.
                       Files will be downloaded to directory download_root_dir/ShortName/.
                       If not specified, parent directory defaults to '~/Downloads/ECCO_V4r4_PODAAC/'.
    
    n_workers: int, number of workers to use in concurrent downloads. Benefits typically taper off above 5-6.
    
    force_redownload: bool, if True, existing files will be redownloaded and replaced;
                            if False, existing files will not be replaced.
    
    return_downloaded_files: bool, if True, string or list of downloaded file(s) (including files that were 
                             already on disk and not replaced) is returned.
                             If False (default), the function returns nothing.

    Returns
    -------
    downloaded_files: str or list, downloaded file(s) with local path that can be passed 
                      directly to xarray (open_dataset or open_mfdataset).
                      Only returned if return_downloaded_files=True.
    
    """

    pass
    
    from concurrent.futures import ThreadPoolExecutor
 

    # set default download parent directory
    if download_root_dir==None:
        download_root_dir = join(expanduser('~'),'Downloads','ECCO_V4r4_PODAAC')

    # define the directory where the downloaded files will be saved
    download_dir = Path(download_root_dir) / ShortName
    
    # create the download directory
    download_dir.mkdir(exist_ok = True, parents=True)
    
    print(f'created download directory {download_dir}')
    
    # get list of files
    s3_files_list = ecco_podaac_s3_query(ShortName,StartDate,EndDate)
    
    num_grans = len(s3_files_list)
    print (f'\nTotal number of matching granules: {num_grans}')

    # initiate S3 access
    s3 = init_S3FileSystem()

    # download files
    downloaded_files = download_files_wrapper(s3, s3_files_list, download_dir, n_workers, force_redownload)
    
    if return_downloaded_files == True:
        if len(downloaded_files) == 1:
            # if only 1 file is downloaded, return a string of filename instead of a list
            downloaded_files = downloaded_files[0]
        return downloaded_files



###================================================================================================================


def ecco_podaac_s3_get_diskaware(ShortNames,StartDate,EndDate,max_avail_frac=0.5,snapshot_interval=None,\
                                 download_root_dir=None,n_workers=6,force_redownload=False):
    
    """
    
    This function estimates the storage footprint of ECCO datasets, given ShortName(s), a date range, and which 
    files (if any) are already present.
    If the footprint of the files to be downloaded (not including files already on the instance or re-downloads) 
    is <= the max_avail_frac specified of the instance's available storage, they are downloaded and stored locally 
    on the instance (hosting files locally typically speeds up loading and computation).
    Otherwise, the files are "opened" using ecco_podaac_s3_open so that they can be accessed directly 
    on S3 without occupying local storage.

    Parameters
    ----------
    
    ShortNames: str or list, the ShortName(s) that identify the dataset on PO.DAAC.
    
    StartDate,EndDate: str, in 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' format, 
                       define date range [StartDate,EndDate] for download.
                       EndDate is included in the time range (unlike typical Python ranges).
                       ECCOv4r4 date range is '1992-01-01' to '2017-12-31'.
                       For 'SNAPSHOT' datasets, an additional day is added to EndDate to enable closed budgets
                       within the specified date range.

    max_avail_frac: float, maximum fraction of remaining available disk space to use in storing current ECCO datasets.
                    This determines whether the dataset files are stored on the current instance, or opened on S3.
                    Valid range is [0,0.9]. If number provided is outside this range, it is replaced by the closer 
                    endpoint of the range.

    snapshot_interval: ('monthly', 'daily', or None), if snapshot datasets are included in ShortNames, 
                       this determines whether snapshots are included for only the beginning/end of each month 
                       ('monthly'), or for every day ('daily').
                       If None or not specified, defaults to 'daily' if any daily mean ShortNames are included 
                       and 'monthly' otherwise.

    download_root_dir: str, defines parent directory to download files to.
                       Files will be downloaded to directory download_root_dir/ShortName/.
                       If not specified, parent directory defaults to '~/Downloads/ECCO_V4r4_PODAAC/'.
    
    n_workers: int, number of workers to use in concurrent downloads. Benefits typically taper off above 5-6.
               Applies only if files are downloaded.
    
    force_redownload: bool, if True, existing files will be redownloaded and replaced;
                            if False, existing files will not be replaced.
                            Applies only if files are downloaded.
    
    
    Returns
    -------
    retrieved_files: dict, with keys: ShortNames and values: downloaded or opened file(s) with path on local instance 
                     or on S3, that can be passed directly to xarray (open_dataset or open_mfdataset).
    
    """

    pass

    import shutil    

    # force max_avail_frac to be within limits [0,0.9]
    max_avail_frac = np.fmin(np.fmax(max_avail_frac,0),0.9)
    
    # initiate S3 access
    s3 = init_S3FileSystem()

    # determine value of snapshot_interval if None or not specified
    if snapshot_interval == None:
        snapshot_interval = 'monthly'
        for curr_shortname in ShortNames:
            if 'DAILY' in curr_shortname:
                snapshot_interval = 'daily'
                break

    # set default download parent directory
    if download_root_dir==None:
        download_root_dir = join(expanduser('~'),'Downloads','ECCO_V4r4_PODAAC')

    # add up total size of files that would be downloaded
    dataset_sizes = np.array([])
    s3_files_list_all = []
    for curr_shortname in ShortNames:
        
        # get list of files
        s3_files_list = ecco_podaac_s3_query(curr_shortname,StartDate,EndDate)

        # for snapshot datasets with monthly snapshot_interval, only include snapshots at beginning/end of months
        if (('SNAPSHOT' in curr_shortname) and (snapshot_interval == 'monthly')):
            s3_files_list_copy = list(tuple(s3_files_list))
            for s3_file in s3_files_list:
                snapshot_date = re.findall("_[0-9]{4}-[0-9]{2}-[0-9]{2}",url)[0][1:]
                if snapshot_date[8:] != '01':
                    s3_files_list_copy.remove(s3_file)
            s3_files_list = s3_files_list_copy
            
        # compute size of current dataset
        download_dir = Path(download_root_dir) / curr_shortname
        curr_dataset_size = 0
        for s3_file in s3_files_list:
            if isfile(join(download_dir,basename(s3_file))) == False:
                curr_dataset_size += s3.info(s3_file)['size']

        dataset_sizes = np.append(dataset_sizes,curr_dataset_size)
        s3_files_list_all.append(s3_files_list)
            

    # query available disk space at download location
    query_disk_completed = False
    query_dir = [download_root_dir][0]
    while query_disk_completed == False:
        try:
            avail_storage = shutil.disk_usage(query_dir).free
            query_disk_completed = True
        except:
            try:
                query_dir = join(*os.path.split(query_dir)[:-1])
            except:                
                print('Error: can not detect available disk space for download_root_dir: '+download_root_dir)
                return -1

    # fraction of available storage that would be occupied by downloads
    sizes_sum = np.sum(dataset_sizes)
    avail_frac = sizes_sum/avail_storage

    print(f'Size of files to be downloaded to instance is {(1.e-3)*np.round((1.e3)*sizes_sum/(2**30))} GB,\n'\
                +f'which is {.01*np.round((1.e4)*avail_frac)}% of the {(1.e-3)*np.round((1.e3)*avail_storage/(2**30))} GB available storage.')

    retrieved_files = {}
    if avail_frac <= max_avail_frac:
        # proceed with file downloads
        print('Proceeding with file downloads from S3')
        for curr_shortname,s3_files_list in zip(ShortNames,s3_files_list_all):
            # set default download parent directory
            if download_root_dir==None:
                download_root_dir = join(expanduser('~'),'Downloads','ECCO_V4r4_PODAAC')
        
            # define the directory where the downloaded files will be saved
            download_dir = Path(download_root_dir) / curr_shortname
            
            # create the download directory
            download_dir.mkdir(exist_ok = True, parents=True)
            
            print(f'created download directory {download_dir}')

            # download files
            downloaded_files = download_files_wrapper(s3, s3_files_list, download_dir, n_workers, force_redownload)

            if len(downloaded_files) == 1:
                # if only 1 file is downloaded, return a string of filename instead of a list
                downloaded_files = downloaded_files[0]

            retrieved_files[curr_shortname] = downloaded_files

    else:
        # open files from S3 instead of downloading
        print('Download size is larger than specified fraction of available storage.\n'\
              +'Generating file lists to open directly from S3.')

        for curr_shortname,s3_files_list in zip(ShortNames,s3_files_list_all):
            # open files and create list that can be passed to xarray file opener
            open_files = [s3.open(file) for file in s3_files_list]
            # if list has length 1, return a string instead of a list
            if len(open_files) == 1:
                open_files = open_files[0]

            retrieved_files[curr_shortname] = open_files

    return retrieved_files