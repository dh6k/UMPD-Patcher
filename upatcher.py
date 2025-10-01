import os
import re
import zipfile
import subprocess
import argparse
from typing import List

def run_command(command: List[str], error_message: str):
    """
    Runs a shell command and raises an exception if it fails.
    """
    print(f"Executing: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed! Stderr: {result.stderr}")
        raise RuntimeError(f"{error_message}: {result.stderr}")
    print(result.stdout)
    print("Command successful.")

def setup_environment(keystore_url: str) -> str:
    """
    Sets up the necessary tools like apktool and uber-apk-signer.
    """
    print("Setting up the environment...")
    run_command(["sudo", "apt-get", "update"], "Failed to update apt")
    run_command(["sudo", "apt-get", "install", "openjdk-8-jre-headless", "-y"], "Failed to install OpenJDK 8")
    apktool_url = "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool"
    apktool_jar_url = "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar"
    run_command(["wget", "-q", apktool_url, "-O", "apktool"], "Failed to download apktool script")
    run_command(["wget", "-q", apktool_jar_url, "-O", "apktool.jar"], "Failed to download apktool JAR")
    os.makedirs("/usr/local/bin", exist_ok=True)
    os.rename("apktool", "/usr/local/bin/apktool")
    os.rename("apktool.jar", "/usr/local/bin/apktool.jar")
    run_command(["sudo", "chmod", "+x", "/usr/local/bin/apktool"], "Failed to set execute permissions on apktool script")
    uber_signer_url = "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
    run_command(["wget", "-q", uber_signer_url, "-O", "uber-apk-signer.jar"], "Failed to download uber-apk-signer")
    keystore_filename = "debug.keystore"
    run_command(["wget", "-q", keystore_url, "-O", keystore_filename], "Failed to download debug.keystore")
    
    print("Environment setup complete!")
    print("-" * 30)
    return keystore_filename

def download_and_decompile(base_apk_dlink: str, split_apk_dlink: str):
    """
    Downloads and decompiles the base and split APKs.
    Returns the names of the decompiled directories.
    """
    print("Downloading and decompiling APKs...")

    run_command(["wget", "-q", base_apk_dlink, "-O", "base.apk"], "Failed to download base APK")
    run_command(["wget", "-q", split_apk_dlink, "-O", "split.apk"], "Failed to download split APK")

    run_command(["apktool", "d", "base.apk"], "Failed to decompile base APK")
    run_command(["apktool", "d", "split.apk"], "Failed to decompile split APK")
    

    base_decompile_folder = "base"
    split_decompile_folder = "split"

    print(f"Decompiled base to: {base_decompile_folder}")
    print(f"Decompiled split to: {split_decompile_folder}")

    print("Decompilation complete!")
    print("-" * 30)
    
    return base_decompile_folder, split_decompile_folder

def modify_files(libmain_url: str, split_decompile_folder: str):
    """
    Renames the original file and replaces it with the modded file.
    """
    print("🛠️ Modifying files...")

    mod_dir = os.path.join(split_decompile_folder, "lib/arm64-v8a")
    orig_file = os.path.join(mod_dir, "libmain.so")
    new_orig_file = os.path.join(mod_dir, "libmain_orig.so")
    mod_file_path = os.path.join(mod_dir, "libmain.so")

    if os.path.exists(orig_file):
        os.rename(orig_file, new_orig_file)
        print(f"Renamed {orig_file} to {new_orig_file}")

    run_command(["wget", "-q", libmain_url, "-O", mod_file_path], "Failed to download modded libmain.so")
    print("File modification complete!")
    print("-" * 30)

def recompile_and_sign(base_folder: str, split_folder: str, output_dir: str, keystore_path: str):
    """
    Recompiles and signs the modified APKs using the provided debug.keystore.
    """
    print("Recompiling and signing APKs...")

    base_out_path = os.path.join(output_dir, "base_recompiled.apk")
    split_out_path = os.path.join(output_dir, "split_recompiled.apk")

    run_command(["apktool", "b", base_folder, "-o", base_out_path], "Failed to recompile base APK")
    run_command(["apktool", "b", split_folder, "-o", split_out_path], "Failed to recompile split APK")

    if not os.path.exists(keystore_path):
        raise FileNotFoundError(f"Keystore not found: {keystore_path}")

    keystore_alias = "androiddebugkey"
    keystore_pass = "android"
    key_pass = "android"

    run_command([
        "java", "-jar", "uber-apk-signer.jar",
        "--apks", base_out_path,
        "--ks", keystore_path,
        "--ksAlias", keystore_alias,
        "--ksPass", keystore_pass,
        "--ksKeyPass", key_pass
    ], "Failed to sign base APK with custom debug.keystore")

    run_command([
        "java", "-jar", "uber-apk-signer.jar",
        "--apks", split_out_path,
        "--ks", keystore_path,
        "--ksAlias", keystore_alias,
        "--ksPass", keystore_pass,
        "--ksKeyPass", key_pass
    ], "Failed to sign split APK with custom debug.keystore")

    print("Recompilation and signing complete!")
    print("-" * 30)

def finalize_apks(directory: str):
    """
    Renames and moves the signed APKs to the final directory.
    """
    print("Finalizing APKs...")
    
    signed_base = os.path.join(directory, "base_recompiled-aligned-signed.apk")
    signed_split = os.path.join(directory, "split_recompiled-aligned-signed.apk")
    
    final_dir = os.path.join(directory, "final")
    os.makedirs(final_dir, exist_ok=True)
    
    if not os.path.exists(signed_base):
        raise FileNotFoundError(f"Missing signed base APK: {signed_base}. Check uber-apk-signer output name.")
    if not os.path.exists(signed_split):
        raise FileNotFoundError(f"Missing signed split APK: {signed_split}. Check uber-apk-signer output name.")
    
    os.rename(signed_base, os.path.join(final_dir, "base.apk"))
    os.rename(signed_split, os.path.join(final_dir, "config.arm64_v8a.apk"))

    print("Finalization complete!")
    print("-" * 30)

def create_xapk(folder_path: str, output_xapk_path: str):
    """
    Creates an XAPK file from a folder of APKs.
    """
    print("Building XAPK file...")

    with zipfile.ZipFile(output_xapk_path, 'w', zipfile.ZIP_DEFLATED) as xapk:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                xapk.write(file_path, arcname)

    print(f"XAPK file created: {output_xapk_path}")
    print("-" * 30)

def main():
    parser = argparse.ArgumentParser(description="Patch and bundle Umamusume APKs for GitHub Actions.")
    parser.add_argument("--baseapk_dlink", type=str, required=True, help="URL to the base APK.")
    parser.add_argument("--splitapk_dlink", type=str, required=True, help="URL to the split APK.")
    parser.add_argument("--libmain_url", type=str, required=True, help="URL to the patched libmain.so file.")
    parser.add_argument("--keystore_url", type=str, required=True, help="URL to the debug keystore")
    args = parser.parse_args()

    final_output_dir = "./final"
    output_xapk_name = "umamusume.xapk"

    try:
        keystore_path = setup_environment(args.keystore_url)
        base_decompile_dir, split_decompile_dir = download_and_decompile(args.baseapk_dlink, args.splitapk_dlink)
        modify_files(args.libmain_url, split_decompile_dir)
        recompile_and_sign(base_decompile_dir, split_decompile_dir, ".", keystore_path)
        finalize_apks(".")
        create_xapk(final_output_dir, output_xapk_name)
        print("Process complete! The patched XAPK is ready.")
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    main()
