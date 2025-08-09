from __future__ import print_function
import os, sys, glob, platform, subprocess, hashlib, shutil

def validate_python_version():
    if sys.version_info < (2, 7):
        sys.exit("Python 2.7 or higher is required.")

def get_iso_directory():
    return sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

def validate_directory(path):
    if not os.path.isdir(path):
        sys.exit("Directory does not exist: {}".format(path))
    if platform.system() == "Linux" and os.geteuid() != 0:
        print("Warning: Root privileges recommended for mounting on Linux.")

def get_os_info():
    system = platform.system()
    if system == "Windows":
        return {
            "os": "Windows",
            "mount": "Mount-DiskImage",
            "unmount": "Dismount-DiskImage"
        }
    elif system == "Linux":
        return {
            "os": "Linux",
            "mount_point": "/mnt/iso"
        }
    else:
        sys.exit("Unsupported OS: {}".format(system))

def compute_file_hash(filepath):
    try:
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print("Error hashing {}: {}".format(filepath, e))
        return None

def write_hash(hash_value, label, hashfile, seen):
    line = "{}  {}\n".format(hash_value, label)
    if line not in seen:
        with open(hashfile, 'a') as f:
            f.write(line)
        seen.add(line)
        print("✔", label)

def hash_local_files(extensions, hashfile, seen):
    for ext in extensions:
        for filename in glob.glob(ext):
            full_path = os.path.abspath(filename)
            hash_val = compute_file_hash(full_path)
            if hash_val:
                write_hash(hash_val, filename, hashfile, seen)

def hash_iso_contents(iso_path, hashfile, seen, os_info):
    iso_name = os.path.basename(iso_path)
    print("\n Processing ISO:", iso_name)

    if os_info["os"] == "Linux":
        mount_point = os_info["mount_point"]
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        try:
            subprocess.call(["sudo", "mount", "-o", "loop", iso_path, mount_point])
            for file in os.listdir(mount_point):
                full_path = os.path.join(mount_point, file)
                if os.path.isfile(full_path):
                    h = compute_file_hash(full_path)
                    if h:
                        write_hash(h, "{}:{}".format(iso_name, file), hashfile, seen)
        finally:
            subprocess.call(["sudo", "umount", mount_point])
            shutil.rmtree(mount_point, ignore_errors=True)

    elif os_info["os"] == "Windows":
        subprocess.call([
            "powershell", "-Command",
            "{} -ImagePath '{}'".format(os_info["mount"], iso_path)
        ], stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)

        get_letter = [
            "powershell", "-Command",
            "(Get-Volume -DiskImage (Get-DiskImage -ImagePath '{}')).DriveLetter".format(iso_path)
        ]
        drive = subprocess.check_output(get_letter).decode().strip().strip('"\'')
        if drive and drive[0].isalpha():
            mount_path = "{}:\\".format(drive[0])
            for file in os.listdir(mount_path):
                full_path = os.path.join(mount_path, file)
                if os.path.isfile(full_path):
                    h = compute_file_hash(full_path)
                    if h:
                        write_hash(h, "{}:{}".format(iso_name, file), hashfile, seen)
        subprocess.call([
            "powershell", "-Command",
            "{} -ImagePath '{}'".format(os_info["unmount"], iso_path)
        ], stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)

def process_all_isos(iso_dir, hashfile, seen, os_info):
    iso_files = glob.glob(os.path.join(iso_dir, "*.iso"))
    if not iso_files:
        print("No ISO files found.")
        return
    for iso_path in iso_files:
        iso_name = os.path.basename(iso_path)
        if "signed" in iso_name.lower():
            hash_iso_contents(iso_path, hashfile, seen, os_info)
        else:
            print(" Skipped (not signed):", iso_name)

def main():
    validate_python_version()
    iso_dir = get_iso_directory()
    validate_directory(iso_dir)
    os_info = get_os_info()

    hashfile = "ISO_Hashes.txt"
    seen_hashes = set()
    with open(hashfile, 'w') as f:
        f.write("ISO Hash Log\n")
    seen_hashes.add("ISO Hash Log\n")

    hash_local_files(["*.iso", "*.sig", "*.pdf"], hashfile, seen_hashes)
    process_all_isos(iso_dir, hashfile, seen_hashes, os_info)
    print("\n Done! Hashes saved to:", os.path.abspath(hashfile))

if __name__ == "__main__":
    main()
