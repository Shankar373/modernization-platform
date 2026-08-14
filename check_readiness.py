import shutil
import subprocess

def run_readiness_check():
    dotnet_path = shutil.which("dotnet")
    print("==================================================")
    print("SystemaOps C# Modernization Engine Readiness Check")
    print("==================================================")
    if dotnet_path:
        print("Status: READY")
        print(f"dotnet CLI location: {dotnet_path}")
        try:
            version = subprocess.check_output(["dotnet", "--version"], text=True).strip()
            print(f".NET SDK Version: {version}")
        except Exception:
            print(".NET SDK Version: Error retrieving version")
        print("Capabilities: C# build / Roslyn execution CAN run.")
    else:
        print("Status: NOT_READY")
        print("dotnet CLI: NOT FOUND (dotnet.exe is not in PATH or standard folders)")
        print("Capabilities: C# build/test status = NOT_AVAILABLE")
        print("Note: syntax validation only. Full compiler compilation requires .NET SDK.")
    print("==================================================")

if __name__ == "__main__":
    run_readiness_check()
