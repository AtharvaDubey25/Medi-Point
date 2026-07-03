import os
import shutil
import sys

def main():
    print("Executing prisma py fetch...")
    # Trigger the download of the Prisma query engine binary
    exit_code = os.system("python -m prisma py fetch")
    if exit_code != 0:
        print("Warning: prisma py fetch exited with non-zero status.")

    # Search paths for the query engine
    search_dirs = [
        "/opt/render/.cache/prisma-python",
        os.path.expanduser("~/.cache/prisma-python"),
        "/opt/render/project"
    ]
    
    found_binaries = []
    
    print("Searching for prisma-query-engine binaries...")
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if "prisma-query-engine-" in file:
                    full_path = os.path.join(root, file)
                    found_binaries.append(full_path)

    if not found_binaries:
        print("Error: Could not find any prisma-query-engine binaries in cache search paths!", file=sys.stderr)
        sys.exit(1)

    # Copy all found query engines directly to the current working directory (backend/)
    dest_dir = os.getcwd()
    for bin_path in found_binaries:
        bin_name = os.path.basename(bin_path)
        dest_path = os.path.join(dest_dir, bin_name)
        try:
            shutil.copy(bin_path, dest_path)
            # Ensure it is executable
            os.chmod(dest_path, 0o755)
            print(f"Successfully copied and set permissions for: {bin_name}")
        except Exception as e:
            print(f"Error copying {bin_name}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
