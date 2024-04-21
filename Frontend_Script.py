import pandas as pd
import streamlit as st
import boto3
import re
from decimal import Decimal  # DynamoDB requires Decimal for numbers
import time
from botocore.exceptions import ClientError  # Import ClientError for handling DynamoDB exceptions
from datetime import date
import os

#contributed by gowthami
def add_bg():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("https://www.boneappetitkitchen.com/cdn/shop/products/IMG_0431_685x.jpg?v=1635127289");
            background-size: cover;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

add_bg()

def inject_custom_styles():
    st.markdown("""
        <style>
        p, ol, ul, dl {
            font-size: 18px;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)

inject_custom_styles()

# Retrieve AWS credentials and region from Streamlit secrets
aws_region = st.secrets["default"]["AWS_REGION"]
aws_access_key_id = st.secrets["default"]["AWS_ACCESS_KEY_ID"]
aws_secret_access_key = st.secrets["default"]["AWS_SECRET_ACCESS_KEY"]


# Initialize DynamoDB resource
if aws_access_key_id and aws_secret_access_key and aws_region:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
else:
    raise ValueError("AWS credentials or region are not set in environment variables.")

table = dynamodb.Table('animals')

# Fetch data from DynamoDB
def get_data_from_dynamodb():
    items = []
    response = table.scan()
    items.extend(response['Items'])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])
    return items

#contributed by laxmikant
def get_max_id_from_dynamodb():
    try:
        # Fetch all items and their IDs from DynamoDB
        response = table.scan(ProjectionExpression="id")
        all_ids = [int(item['id']) for item in response['Items']] if response['Items'] else [0]
        # Continue fetching if more data is available
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression="id",
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            all_ids.extend([int(item['id']) for item in response['Items']])

        # Find the maximum ID
        return max(all_ids)
    except ClientError as e:
        print(f"Error fetching max ID from DynamoDB: {e.response['Error']['Message']}")
        return 0  # Return a default ID of 0 if fetch fails
    
#contributed by sarthak
def create_item_in_dynamodb(item_data):
    try:
        item_data['animalage'] = Decimal(str(item_data['animalage']))  # Convert float to Decimal for DynamoDB
        
        # Ensure other fields are appropriately typed as needed
        response = table.put_item(Item=item_data)
        return True
    except Exception as e:
        st.error(f"Failed to create new entry: {str(e)}")
        return False

#contributed by gowthami
def update_item_in_dynamodb(item_id, updated_fields):
    try:
        update_expression = "SET "
        expression_attribute_names = {}
        expression_attribute_values = {}

        # Convert datetime.date to string and other necessary conversions
        for idx, (key, value) in enumerate(updated_fields.items()):
            placeholder = f"#attr{idx}"
            value_placeholder = f":val{idx}"

            # Check if the value is a date and convert it to string
            if isinstance(value, date):
                value = value.isoformat()  # Converts date to 'YYYY-MM-DD' string format

            expression_attribute_names[placeholder] = key
            expression_attribute_values[value_placeholder] = Decimal(str(value)) if isinstance(value, float) else value
            
            update_expression += f"{placeholder} = {value_placeholder}, "

        update_expression = update_expression.rstrip(", ")

        response = table.update_item(
            Key={'id': int(item_id)},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW"
        )
        return response
    except ClientError as e:
        return f"Update failed: {e.response['Error']['Message']}"

#contributed by sarthak
def delete_item_from_dynamodb(item_id):
    try:
        # Perform the delete operation
        response = table.delete_item(Key={'id': item_id})
        # Check the response status code
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            return "Deleted successfully", None
        else:
            return "Deletion did not succeed", None
    except ClientError as e:
        # Return error message if any
        return None, e.response['Error']['Message']


data = get_data_from_dynamodb()
df = pd.DataFrame(data)
column_order = ['id', 'animalname', 'speciesname', 'breedname', 'sexname', 'animalage',
                'basecolour', 'location', 'sheltercode', 'identichipnumber', 'intakereason',
                'intakedate', 'movementtype', 'movementdate', 'returnedreason',
                'deceasedreason', 'diedoffshelter', 'istransfer', 'istrial', 'puttosleep', 'isdoa']
df = df[column_order]
df.index = df.index + 1
df.columns = ['ID', 'Name', 'Species', 'Breed', 'Sex', 'Age', 'Color', 'Location', 'Shelter Code', 'Chip Number', 'Intake Reason', 'Intake Date', 'Movement Type', 'Movement Date', 'Return Reason', 'Deceased Reason', 'Off Shelter Death', 'Transfer', 'Trial', 'Euthanasia', 'DOA']

# Streamlit UI Layout
st.title('Companion Connect')
st.header("A Data-Driven Platform for Animal Shelter Management and Adoption")

cols = st.columns([5, 1])
with cols[1]:
    action = st.selectbox("Actions:", ["Create", "Read", "Update", "Delete"], key='action_select')
    
#contributed by gowthami
if action == 'Create':

    max_id = get_max_id_from_dynamodb()  # Get the current maximum ID
    new_id = max_id + 1  # Increment the max ID by 1 for the new entry
    
    with st.form("New Animal Form", clear_on_submit=True):
        # Define the specific fields to include in the form
        fields_to_include = [
            ('animalname', 'Name'),
            ('speciesname', 'Species'),
            ('breedname', 'Breed'),
            ('sexname', 'Sex'),
            ('animalage', 'Age'),
            ('basecolour', 'Color'),
            ('intakereason', 'Intake Reason'),
            ('intakedate', 'Intake Date')
        ]

        # Pre-fill the ID field with the new auto-generated ID
        st.text_input("ID", value=new_id, disabled=True)
        
        # Create a list of columns with 4 columns per row
        form_columns = st.columns(4)
        new_animal_data = {}
        index = 0  # Index to manage which column to place the input field
        for field_key, field_label in fields_to_include:
            current_col = form_columns[index % 4]  # Cycle through columns
            if field_key == 'animalage':  # Handle numeric input specifically
                new_animal_data[field_key] = current_col.number_input(field_label, key=field_key, min_value=0.0, step=0.1, format="%.1f")
            elif field_key == 'intakedate':  # Handle date input
                # Convert the date to a string before storing it
                intake_date = current_col.date_input(field_label, key=field_key)
                new_animal_data[field_key] = intake_date.isoformat() if isinstance(intake_date, date) else None
            else:
                new_animal_data[field_key] = current_col.text_input(field_label, key=field_key)
            index += 1  # Increment to place the next field in the next column

        submit_button = st.form_submit_button("Submit")
        
        if submit_button:
            try:
                # Ensure ID is an integer and unique
                new_animal_data['id'] = new_id

                if create_item_in_dynamodb(new_animal_data):
                    st.success("New animal entry created successfully!")
                    data = get_data_from_dynamodb()  # Refresh data
                else:
                    st.error("Failed to create new animal entry.")
            except ValueError:
                st.error("Animal ID must be a number.")
                st.stop()


elif action == 'Update':
    
    update_id = st.text_input("Enter the ID of the animal to update:", key="update_id")
    load_button = st.button('Load')  # Place the "Load" button below the text input

    if update_id:
        
        # Fetch the existing data for the ID
        try:
            response = table.get_item(Key={'id': int(update_id)})
            if 'Item' in response:
                existing_data = response['Item']
            else:
                st.error("No data found for this ID.")
                st.stop()
        except ClientError as e:
            st.error("Failed to fetch data: " + e.response['Error']['Message'])
            st.stop()

        # Create a form for updates
        with st.form("Update Animal Form"):
            # Define fields that can be updated
            fields_to_update_with_labels = [
                        ('animalname', 'Name'),
                        ('speciesname', 'Species'),
                        ('breedname', 'Breed'),
                        ('sexname', 'Sex'),
                        ('animalage', 'Age'),
                        ('basecolour', 'Color'),
                        ('location', 'Location'),
                        ('sheltercode', 'Shelter Code'),
                        ('identichipnumber', 'Chip Number'),
                        ('intakereason', 'Intake Reason'),
                        ('intakedate', 'Intake Date'),
                        ('movementtype', 'Movement Type'),
                        ('movementdate', 'Movement Date'),
                        ('returnedreason', 'Return Reason'),
                        ('deceasedreason', 'Deceased Reason'),
                        ('diedoffshelter', 'Off Shelter Death'),
                        ('istransfer', 'Transfer'),
                        ('istrial', 'Trial'),
                        ('puttosleep', 'Euthanasia'),
                        ('isdoa', 'DOA'),
                    ]
            updated_data = {}

            # Create four columns for the fields
            cols = st.columns(4)
            for index, (field_key, field_label) in enumerate(fields_to_update_with_labels):
                        with cols[index % 4]:
                            if field_key == 'animalage':  # Handle numeric input specifically
                                updated_data[field_key] = st.number_input(field_label, min_value=0.0, step=0.1, format="%.1f", value=float(existing_data.get(field_key, 0)))
                            elif field_key in ['intakedate', 'movementdate']:  # Handle date inputs
                                existing_date = existing_data.get(field_key, '')
                                updated_data[field_key] = st.date_input(field_label, value=date.fromisoformat(existing_date) if existing_date else date.today())
                            else:
                                updated_data[field_key] = st.text_input(field_label, value=existing_data.get(field_key, ''))
                                

            submit_update = st.form_submit_button("Submit")
            if submit_update:
                # Prepare the data for updating in DynamoDB
                update_response = update_item_in_dynamodb(update_id, {k: v for k, v in updated_data.items() if v != existing_data.get(k)})
                if isinstance(update_response, dict):
                    st.success("Animal data updated successfully!")
                else:
                    st.error(update_response)

#contributed by laxmikant
elif action == 'Delete':
    delete_id = st.text_input("Enter the ID of the animal to delete:", key="delete_id")
    delete_button = st.button('Delete')

    if delete_button and delete_id:
        try:
            # Convert delete_id to the correct type, e.g., int or string, based on your table's primary key type
            delete_id = int(delete_id)
            # First, check if the item exists
            response = table.get_item(Key={'id': delete_id})
            if 'Item' not in response:
                st.error(f"No results found for ID: {delete_id}")
            else:
                # If the item exists, then delete it
                success_message, error_message = delete_item_from_dynamodb(delete_id)
                
                if error_message:
                    st.error(f"Error deleting animal: {error_message}")
                else:
                    st.success(success_message)

        except ValueError:
            st.error("Invalid ID type provided.")
            

#contributed by gowthami            
elif action == 'Read':
    st.header("Find Your Companion")
    search_fields = ['Species', 'Breed', 'Color', 'Age', 'Sex', 'Intake Reason']
    search_cols_layout = st.columns(6)

    # Buttons for searching and refreshing
    button_cols = st.columns([1, 1, 4])
    search_clicked = button_cols[0].button('Search')
    refresh_clicked = button_cols[1].button('Refresh')

    # If the "Refresh" button is clicked, clear the fields and rerun
    if refresh_clicked:
        # Set all search fields in session_state to empty strings before any input widgets are created
        for field in search_fields:
            st.session_state[field] = ""
        # Trigger a rerun of the app to reflect the updated state
        st.experimental_rerun()

    # Create the input fields after checking for refresh
    search_values = {}
    for idx, field in enumerate(search_fields):
        search_values[field] = search_cols_layout[idx].text_input(field, value=st.session_state.get(field, ""), key=field)

    # If the "Search" button is clicked, filter the dataframe
    if search_clicked:
        query_df = df.copy()
        for field in search_fields:
            if search_values[field]:
                # Use a raw string to handle regex special characters correctly
                regex_pattern = fr'\b{re.escape(search_values[field])}\b'
                query_df = query_df[query_df[field].str.contains(regex_pattern, case=False, na=False, regex=True)]
        if query_df.empty:
            st.write("No Matches Found")
        else:
            st.dataframe(query_df)
    elif not search_clicked:
        st.dataframe(df)


