import os
import shutil
import sys

def main():
    print("Executing prisma py fetch...")
    exit_code = os.system("python -m prisma py fetch")
    if exit_code != 0:
        print(f"Warning: prisma py fetch exited with code {exit_code}")

    search_dirs = [
        "/opt/render/.cache/prisma-python",
        os.path.expanduser("~/.cache/prisma-python"),
        "/opt/render/project/src/backend"
    ]
    
    found_binaries = []
    
    print("Searching for any query engine files...")
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            print(f"Path does not exist: {search_dir}")
            continue
        print(f"Scanning directory: {search_dir}")
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                # Print all files we see in binaries folder for debugging
                if "binaries" in root or "prisma" in file.lower() or "engine" in file.lower():
                    print(f"Found file in walk: {os.path.join(root, file)}")
                
                # Check for query engine (matches prisma-query-engine-* and query-engine-*)
                if "query-engine" in file:
                    full_path = os.path.join(root, file)
                    found_binaries.append(full_path)

    if not found_binaries:
        print("Error: Could not find any query-engine binaries in cache search paths!", file=sys.stderr)
        sys.exit(1)

    # Copy found query engines to current working directory
    dest_dir = os.getcwd()
    for bin_path in found_binaries:
        bin_name = os.path.basename(bin_path)
        
        # If the file is named query-engine-* but python-prisma wants prisma-query-engine-*,
        # we copy it to both filenames to be absolutely safe!
        dest_filenames = [bin_name]
        if bin_name.startswith("query-engine-"):
            dest_filenames.append("prisma-" + bin_name)
            
        for dest_name in dest_filenames:
            dest_path = os.path.join(dest_dir, dest_name)
            try:
                shutil.copy(bin_path, dest_path)
                os.chmod(dest_path, 0o755)
                print(f"Successfully copied to: {dest_name}")
            except Exception as e:
                print(f"Error copying to {dest_name}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
