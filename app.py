"""App module."""

from os import makedirs, path, scandir

import ipdb
import migrate
import shutil
import requests
import zipfile
# import api

def handler(event, context):
    presigned_download_url = event['presigned_download_url']
    presigned_upload_url = event['presigned_upload_url']
    background_job_id = event['background_job_id']

    import_folder = f"/tmp/import_folder"
    export_folder = f"/tmp/export_folder"
    makedirs(import_folder)
    makedirs(export_folder)

    download_to_file_system(import_folder, presigned_download_url)
    unzip_import_folder(import_folder)
    convert_folder(import_folder, export_folder)
    zip_files(export_folder)
    upload_converted_to_presigned_url(presigned_upload_url)
    # update_background_job(background_job_id)

def download_to_file_system(import_folder, presigned_download_url):
    response = requests.get(presigned_download_url, stream=True)
    if response.status_code == 200:
        with open(f"{import_folder}/download.zip", 'wb') as f:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, f)

def unzip_import_folder(import_folder):
    with zipfile.ZipFile(f"{import_folder}/download.zip","r") as zip_ref:
        zip_ref.extractall(f"{import_folder}/download")  

def convert_folder(import_folder, export_folder):
    migrate.run(f"{import_folder}/download", export_folder)

def zip_files(export_folder):
    shutil.make_archive('/tmp/export', 'zip', export_folder)

def upload_converted_to_presigned_url(presigned_upload_url):
    with open('/tmp/export.zip', 'rb') as data:
        requests.put(presigned_upload_url, data=data)

# def update_background_job(background_job_id):
    
