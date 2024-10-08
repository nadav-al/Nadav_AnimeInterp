import os
from datetime import datetime
import json
from PIL import Image


def get_next_test_number(root_path, folder_base):
    test_dir = os.path.join(root_path, folder_base)
    if not os.path.exists(test_dir):
        return 1

    # existing_tests = [d for d in os.listdir(test_dir) if
    #                   d.startswith("test") and os.path.isdir(os.path.join(test_dir, d))]
    existing_tests = [d.split("_")[0] for d in os.listdir(test_dir) if
                      d.startswith("test")]
    if not existing_tests:
        return 1

    max_test_num = max(int(d[4:]) for d in existing_tests)
    return max_test_num + 1

def extract_string_from_dict(dictionary):
    details = []
    for key, value in dictionary.items():
        if type(value) is bool and value:
            details.append(key)
        elif type(value) is int and value > 1:
            details.append(f"{key}{value}")
    return "_".join(details)

def generate_folder(folder_name=None, folder_base=None, root_path="experiments/checkpoints", test_details=None, unique_folder=False, create=True):
    # Get current date in mm-dd format
    if folder_base is None:
        folder_base = datetime.now().strftime("%m-%d")
    # Get the next test number
    test_num = get_next_test_number(root_path, folder_base)
    if not unique_folder and test_num > 1:
        test_num -= 1

    # Create the full path
    # full_path = os.path.join(root_path, current_date, f"test{test_num}", folder_name)
    test_str = ""
    if test_details:
        if type(test_details) is str:
            test_str = test_details
        else:
            test_str = f"test{test_num}_{extract_string_from_dict(test_details)}"
    if folder_name is not None:
        full_path = os.path.join(root_path, folder_base, test_str, folder_name)
    else:
        full_path = os.path.join(root_path, folder_base, test_str)

    full_path = os.path.normpath(full_path)
    # Create the directory
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)

    print(f"Folder created: {full_path}")
    return full_path


def read_folders_from_json(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Create an array to store all full paths
    folders_list = []

    # Iterate through each root and its folders
    for root, folders in data.items():
        for folder in folders:
            # Combine the root path with the folder name
            full_path = os.path.join(root, folder['folder'])
            # Normalize the path to handle any potential issues with separators
            full_path = os.path.normpath(full_path)
            folders_list.append(full_path)

    return folders_list



def get_folders(root):
    folders = []
    while True:
        folder_name = input(f"Enter folder name for root '{root}' (or press Enter to finish this root): ").strip()
        if not folder_name:
            break
        if not os.path.exists(os.path.join(root, folder_name)):
            print("folder does not exists")
            continue
        folders.append({"folder": folder_name})
    return folders

def write_folders_to_json(output_root="data_groups_jsons"):
    data = dict()

    prefix = input("Enter a prefix to all roots if necessery")

    while True:
        root = input("Enter root folder (or press Enter to finish): ").strip()
        if not root:
            break
        root = os.path.join(prefix, root)
        folders = get_folders(root)
        if folders:  # Only add the root if it has folders
            data[root] = folders

    test_num = get_next_test_number(output_root, "")
    current_date = datetime.now().strftime("%m-%d")
    file_name = f"test{test_num}_{current_date}.json"

    if not os.path.exists(output_root):
        os.makedirs(output_root)

    with open(os.path.join(output_root, file_name), "w") as f:
        json.dump(data, f, indent=2)

    print(f"JSON file '{file_name}' has been created successfully.")


def extract_style_name(file_name):
    prefix = extract_known_prefix(file_name)
    if prefix is None:
        return "Animation"
    elif prefix == "Japan":
        return "Anime"
    return prefix

def extract_known_prefix(file_name):

    if file_name.startswith("Disney"):
        return "Disney"
    elif file_name.startswith("Pixar"):
        return "Pixar"
    elif file_name.startswith("Japan"):
        return "Japan"
    elif file_name.startswith("Anime"):
        return "Anime"
    return None


def remove_style_name(file_name):
    style = extract_style_name(file_name)
    if file_name.startswith(style):  # for cases that style = "Animation" and the file's name doesn't start with "Animation"
        return file_name.replace((style + '_'), "")
    elif style == "Anime":
        return file_name.replace("Japan_", "")
    return file_name

def repeat_data(path, repeats : int, folder_base, test_details, folder_name=None, output_folder=None, unique_folder=False):
    out_path = output_folder
    if output_folder is None:
        # TODO handel generate_folder
        out_path = generate_folder(folder_name=folder_name, folder_base=folder_base, test_details=test_details, root_path="TempDatasets", unique_folder=unique_folder)
    files = os.listdir(path)
    for file in files:
        with Image.open(os.path.join(path, file)) as img:
            for r in range(repeats):
                img.save(os.path.join(out_path, f'{r+1}_{file}'))
    return out_path