"""
Rewritten BenchlingAPI class using Benchling SDK
- Uses benchling SDK instead of manual requests/POST calls
- Keeps boto3 authentication and webhook verification
- Modularized functions for better maintainability
"""

import json
import os
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Any, List, Dict, Optional
from itertools import islice
from pathlib import Path

# Benchling SDK imports
from benchling_sdk.benchling import Benchling
from benchling_sdk.auth.client_credentials_oauth2 import ClientCredentialsOAuth2
from benchling_sdk.models import (
    PlateCreate,
    NamingStrategy,
    PlateUpdate,
    AppSessionUpdate,
    CustomEntityCreate,
    AppSessionMessageCreate,
    AssayResult,
    AssayResultCreate,
    AssayRunUpdate,
    LocationCreate,
    BlobCreateType
)

from benchling_sdk.apps.framework import App
from benchling_sdk.helpers.serialization_helpers import fields
import boto3

# Constants
APP_DEFINITION_ID = "appdef_kd1BeumS5Q"
DEBUG_LEVEL = 0

class WebhookVerificationError(Exception):
    pass

def debug_msg(level: int, message: str):
    """Print debug messages based on debug level"""
    if DEBUG_LEVEL >= level:
        print(message)

class BenchlingAPI:
    """
    Modular BenchlingAPI class using Benchling SDK
    """
    
    def __init__(self, tenant: str, app_name: str = 'automation'):
        """Initialize BenchlingAPI with tenant and app configuration"""
        debug_msg(1, '\n*********************')
        debug_msg(1, 'Initializing Benchling')
        debug_msg(1, '*********************')
        
        self.tenant = tenant
        self._setup_aws_client()
        self._setup_benchling_connection(app_name)
        self._setup_app_session(app_name)
        
        debug_msg(1, f'Tenant: {self.tenant}')
        debug_msg(1, f'Base URL: {self.base_url}')
        debug_msg(1, '*********************')
        debug_msg(1, 'Initialize Complete')
        debug_msg(1, '*********************\n')
    
    def _setup_aws_client(self):
        """Initialize AWS SSM client for parameter retrieval"""
        self.ssm_client = boto3.client('ssm')
    
    def _setup_benchling_connection(self, app_name: str):
        """Setup Benchling SDK connection and load tenant settings"""
        # Determine tenant environment
        tenant_map = {
            'Production': 'prod', 'Prod': 'prod', 'PROD': 'prod', 'prod': 'prod',
            'Test': 'test', 'TEST': 'test', 'test': 'test',
            'Dev': 'dev', 'DEV': 'dev', 'dev': 'dev'
        }
        
        tenant_env = tenant_map.get(self.tenant, 'dev')
        
        # Set base URL
        if tenant_env == 'prod':
            self.base_url = "https://21stbio.benchling.com/api/v2"
        elif tenant_env == 'test':
            self.base_url = "https://21stbiotest.benchling.com/api/v2"
        else:  # dev
            self.base_url = "https://21stbiodev.benchling.com/api/v2"
        
        # Get credentials from AWS SSM
        credentials = self._get_aws_credentials(tenant_env, app_name)
        if not credentials:
            raise Exception("Failed to obtain credentials")
        
        # Setup Benchling SDK authentication
        auth_method = ClientCredentialsOAuth2(
            client_id=credentials['client_id'],
            client_secret=credentials['client_secret'],
            token_url=f"{self.base_url}/token"
        )
        
        self.benchling = Benchling(url=self.base_url, auth_method=auth_method)
        self.access_token = credentials['access_token']
        self.REGISTRY_ID = credentials['registry_id']
        
        # Load additional parameters
        self._load_tenant_parameters(tenant_env)
    
    def _get_aws_credentials(self, tenant_env: str, app_name: str) -> Optional[Dict]:
        """Get credentials from AWS SSM parameters"""
        try:
            client_id = self.ssm_client.get_parameter(
                Name=f'/BL/{tenant_env}/app/{app_name}_client_id', 
                WithDecryption=True
            )['Parameter']['Value']
            
            client_secret = self.ssm_client.get_parameter(
                Name=f'/BL/{tenant_env}/app/{app_name}_client_secret', 
                WithDecryption=True
            )['Parameter']['Value']
            
            registry_id = self.ssm_client.get_parameter(
                Name=f'/BL/{tenant_env}/registry_id', 
                WithDecryption=True
            )['Parameter']['Value']
            
            # Get access token manually for compatibility
            access_token = self._get_access_token(client_id, client_secret)
            
            return {
                'client_id': client_id,
                'client_secret': client_secret,
                'registry_id': registry_id,
                'access_token': access_token
            }
            
        except Exception as e:
            debug_msg(1, f"Error getting credentials: {e}")
            return None
    
    def _get_access_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """Get access token for compatibility with existing verify method"""
        import requests
        
        url = f"{self.base_url}/token"
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(url, data=data, headers=headers)
            response.raise_for_status()
            return response.json().get('access_token')
        except Exception as e:
            debug_msg(1, f"Error getting access token: {e}")
            return None
    
    def _load_tenant_parameters(self, tenant_env: str):
        """Load tenant-specific parameters from AWS SSM"""
        parameter_names = [
            f'/BL/{tenant_env}/folder/automations',
            f'/BL/{tenant_env}/dropdown/plate_type',
            f'/BL/{tenant_env}/schema_id/96_well_plate',
            #f'/BL/{tenant_env}/inventory/development_testing',
            #f'/BL/{tenant_env}/schema_id/Hypothetical_Location',
            #f'/BL/{tenant_env}/schema_id/Hypothetical_Location',
        ]
        
        # Load parameters in batches (AWS limit: 10 per request)
        def batch_params(params: List[str], size: int = 10):
            iterator = iter(params)
            while True:
                chunk = list(islice(iterator, size))
                if not chunk:
                    break
                yield chunk
        
        all_parameters = []
        for batch_names in batch_params(parameter_names):
            try:
                response = self.ssm_client.get_parameters(Names=batch_names, WithDecryption=True)
                all_parameters.extend(response['Parameters'])
                if response.get('InvalidParameters'):
                    debug_msg(1, f"Invalid parameters: {response['InvalidParameters']}")
            except Exception as e:
                debug_msg(1, f"Error loading parameters: {e}")
        
        # Set parameters as class attributes
        for param in all_parameters:
            key = param['Name']
            value = param['Value']
            attr_name = key.split('/')[-2].upper() + '_' + key.split('/')[-1].upper()
            setattr(self, attr_name, value)
    
    def _setup_app_session(self, app_name: str):
        """Setup app session using Benchling SDK"""
        try:
            app_list = self.benchling.apps.list_apps(name=app_name)
            if app_list:
                app_id = app_list.first().id
                self.app = App(app_id, self.benchling)
            else:
                debug_msg(1, f"App '{app_name}' not found")
                self.app = None
        except Exception as e:
            debug_msg(1, f"Error setting up app session: {e}")
            self.app = None
    
    
    # --- Assay Results Methods ---
    def bulk_get_plates_contents_id_name_and_barcode_from_barcodes(self, plate_barcodes: List[str]) -> Dict[str, tuple[str, str]]:
        """
        Get plate contents (ID, name, barcode) for a list of plate barcodes using SDK

        Args:
            plate_ids: List of plate barcodess
            
        Returns:
            Dictionary mapping 'plate_id:well_position' to (plate_id, plate_name, barcode)
        """
        try:
            pages = self.benchling.plates.list(barcodes=plate_barcodes)
            well_contents = {}

            for page in pages:
                for plate in page:
                    for well_position in plate.wells.additional_properties.keys():
                        well = plate.wells.additional_properties[well_position]
                        #print(well.contents[0])
                        well_contents[well.barcode] = (
                            well.contents[0].entity.id, 
                            well.contents[0].entity.name, 
                            well.contents[0].entity.entity_registry_id
                        )
            #print(well_contents)  
            return well_contents
            
        except Exception as e:
            debug_msg(1, f"Error getting plates contents: {e}")
            return {}
        
    
    def create_results_from_dataframe(self, df: pd.DataFrame, schema_id: str, project_id: str) -> List[AssayResult]:
        """
        Create AssayResult objects from a DataFrame
        :param df: DataFrame containing assay data
        :param schema_id: Benchling schema ID for the assay results
        :param project_id: Benchling project ID for the assay results
        :return: List of AssayResult objects
        """
        results = [
            AssayResultCreate(
                schema_id=schema_id,
                project_id=project_id,
                fields=fields({
                    col: {"value": row[col]} for col in df.columns
                })
            ) for _, row in df.iterrows()
        ]
            
        print(f"🔄 Bulk uploading {len(results)} SN results to Benchling...")
        print(results)
        # Bulk create all at once
        task_response = self.benchling.assay_results.bulk_create(results)
        task_id = task_response.task_id
        print(f"📋 Task ID: {task_id}")
        self.benchling.tasks.wait_for_task(task_id)
        response = self.benchling.tasks.get_by_id(task_id)
        return response
    
    def get_dropdown_option_api_id(self, dropdown_name: str, option_name: str) -> Optional[str]:
        """Get dropdown option API ID using SDK"""
        try:
            
            pages=self.benchling.dropdowns.list(page_size=200)
            for page in pages:
                for dropdown in page:
                    if dropdown.name==dropdown_name:
                        dropdown_id=dropdown.id
                        break
            dropdown = self.benchling.dropdowns.get_by_id(dropdown_id)
            for option in dropdown.options:
                if option.name == option_name:
                    return option.id
            return None
        except Exception as e:
            debug_msg(1, f"Error getting dropdown option: {e}")
            return None
    # Location Methods-----------------------
    def create_location_if_not_exists(self, name: str, parent_storage_id: str):
        loc_id=None
        pages=self.benchling.locations.list(names_any_of=[name])
        for page in pages:
            for loc in page:
                loc_id=loc.id
            break
        if not loc_id:
            location = self.benchling.locations.create(LocationCreate(name=name, schema_id=self.SCHEMA_ID_HYPOTHETICAL_LOCATION, parent_storage_id=parent_storage_id))
            print(f"Created location: {location.id}")
        else:
            print(f"Location already exists: {loc_id}")
        return loc_id

    def get_plate_api_id(self, plate_barcode: str) -> Optional[str]:
        """Get plate API ID by barcode using SDK"""
        try:
            plates = self.benchling.plates.list(barcodes=[plate_barcode])
            if plates:
                return plates.first().id
            return None
        except Exception as e:
            debug_msg(1, f"Error getting plate API ID: {e}")
            return None

    def upload_picture_blob(self, file_path, blob_name: str) -> Optional[str]:
        """Upload blob using SDK - simplest version"""
        path_obj = Path(file_path)
        blob = self.benchling.blobs.create_from_file(file_path=path_obj, name=blob_name, blob_type=BlobCreateType.VISUALIZATION)
        return blob.id

    def attach_images_to_plate(self, plate_barcode: str, image_paths: List[str]):
        """Attach images to plate"""
        plate_id = self.get_plate_api_id(plate_barcode)
        if not plate_id:
            print(f"Plate {plate_barcode} not found in Benchling")
            return False

        plate = self.benchling.plates.get_by_id(plate_id)
        images = plate.fields.additional_properties["Image"].value 

        for image_path in image_paths:
            blob_id = self.upload_picture_blob(image_path, Path(image_path).name)
            if blob_id:
                images.append(blob_id)

        if images:
            result = self.benchling.plates.update(plate_id=plate_id, plate=PlateUpdate(fields=fields({"Image": {"value": images}})))
            print(f'Updated plate result: {result}')
            return True
        return False
    def create_fermentation_process_profile(self, profile_type: str, profile_json: Dict,  image_path: str):
        """Create fermentation process profile custom entity"""
        try:
            type_api_id=test_api.get_dropdown_option_api_id('Ferm Profile Type',profile_type)
            blob_id = self.upload_picture_blob(image_path, f'{profile_type} Profile.png')
            ferm_process_profile = self.benchling.custom_entities.create(
                entity=CustomEntityCreate(
                    schema_id='ts_Z5ZMbKkAkL', 
                    name='Ferm Profile',
                    registry_id=self.REGISTRY_ID,
                    naming_strategy=NamingStrategy.REPLACE_NAMES_FROM_PARTS,
                    fields=fields({
                        'JSON Profile': {'value': json.dumps(profile_json)},
                        'Type': {'value': type_api_id},
                        'Profile Image': {'value': blob_id}
                    })
                )
            )
            return ferm_process_profile
        except Exception as e:
            debug_msg(1, f"Error creating fermentation process profile: {e}")
            return None
# Example usage
profile_json={
  "profile": [
    {
      "type": "constant",
      "setpoint": 0,
      "duration": 5,
      "parameter": "Stir speed_SP (rpm)"
    },
    {
      "type": "ramp",
      "start_temp": 500,
      "end_temp": 1550,
      "duration": 13.13,
      "parameter": "Stir speed_SP (rpm)"
    },
    {
      "type": "constant",
      "setpoint": 1550,
      "duration": 146.56,
      "parameter": "Stir speed_SP (rpm)"
    }
  ]
}
if __name__ == "__main__":
    # Test the rewritten API
    test_api = BenchlingAPI('Test', 'automation')

    # Get all JSON profiles from Benchling
    profile_jsons = []
    pages = test_api.benchling.custom_entities.list(schema_id='ts_Z5ZMbKkAkL')
    for page in pages:
        for entity in page:
            json_string = entity.fields.additional_properties['JSON Profile'].value
            profile_jsons.append(json.loads(json_string))  # Parse JSON string to dict

    # Now profile_jsons is a list of dictionaries, not JSON strings
    print(f"Found {len(profile_jsons)} profiles")

    # Example: Check if a new profile already exists
    new_profile = {
        "profile": [
            {"type": "constant", "setpoint": 25, "duration": 5, "parameter": "Temperature"},
            {"type": "ramp", "start_temp": 25, "end_temp": 37, "duration": 2, "parameter": "Temperature"}
        ]
    }

    # Method 1: Simple comparison (exact match)
    profile_exists = new_profile in profile_jsons
    print(f"Profile exists (exact match): {profile_exists}")

    # Method 2: Compare just the profile components
    for i, existing_profile in enumerate(profile_jsons):
        if existing_profile.get('profile') == new_profile.get('profile'):
            print(f"Found matching profile at index {i}")
            break
    else:
        print("No matching profile found")
    #test_api.bulk_get_plates_contents_id_name_and_barcode_from_barcodes(['96WP934'])
    #df=pd.DataFrame({'sample': ['bfi_sSdeNLKpNy', 'bfi_k0DN4pvpVv'], 'raw_luminescence': [100, 200]})
    #print(test_api.FOLDER_AUTOMATIONS)
#print(test_api.create_results_from_dataframe(df,'assaysch_7uzSlHiB','src_UizUYd9d'))
    #name = "Test Create Location Function"
    #parent_storage_id = "loc_9rHbvHDc"
    #test_api.create_location_if_not_exists(name, parent_storage_id)
    #locsch_sj5DEuN7
    #prod_api = BenchlingAPI('Production', 'automation')
    #print(test_api.get_entry_template_table_ids('tmpl_7zOajxSJ'))
    
    #with test_api.app.create_session_context(name="Test Session", timeout_seconds=120) as session:
    #    test_api.log_to_benchling(session, "Test log message")
    #print(test_api.bulk_get_plates_contents_id_name_and_barcode_from_ids(['plt_HaVEHWkc']))