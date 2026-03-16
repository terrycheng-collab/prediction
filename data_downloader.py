from pathlib import Path
import requests
import tarfile
import zstandard as zstd
from tqdm import tqdm
import shutil

def download_and_extract_data(url: str, archive_name: str, output_dir: str):
    """
    Downloads a compressed archive (Zstandard-compressed tar) from a remote URL
    and extracts it to the specified output directory.

    Parameters:
        url (str): The URL of the compressed archive.
        archive_name (str): The name of the archive file to save locally.
        output_dir (str): The directory where the extracted files will be saved.
    """
    archive_path = Path(archive_name)
    tar_path = Path(archive_name.replace(".zst", ""))
    out_dir = Path(output_dir)
    data_dir = out_dir / "data"

    # If the dataset has already been extracted, skip download/extraction
    if data_dir.exists() and any(data_dir.rglob("*.parquet")):
        print(f"Data directory already exists at {data_dir}; skipping download and extraction.")
        return

    # Download the compressed archive with progress bar
    if not archive_path.exists():
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            with open(archive_path, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc="Downloading"
            ) as pbar:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        print("Archive downloaded.")
    else:
        print(f"Archive already exists at {archive_path}; skipping download.")

    # Decompress .zst → .tar
    if not tar_path.exists():
        dctx = zstd.ZstdDecompressor()
        with open(archive_path, "rb") as compressed, open(tar_path, "wb") as destination:
            dctx.copy_stream(compressed, destination)
        print("Archive decompressed.")
    else:
        print(f"Decompressed tar already exists at {tar_path}; skipping decompression.")

    # Extract tar file to workspace root
    if not data_dir.exists():
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=out_dir)
        print("Done. Dataset extracted.")
    else:
        print(f"Data directory already exists at {data_dir}; skipping extraction.")

def verify_and_clean_extraction(url: str, archive_name: str, output_dir: str, force_clean: bool = False):
    """
    Verifies the integrity of the downloaded archive and cleans up any partial
    extraction artifacts before performing a fresh extraction.

    Parameters:
        url (str): The URL of the compressed archive.
        archive_name (str): The name of the archive file to verify.
        output_dir (str): The directory where the extracted files will be saved.
        force_clean (bool): If True, forces re-extraction by deleting existing data.
    """
    archive = Path(archive_name)
    partial_tar = Path(archive_name.replace(".zst", ""))
    data_dir = Path(output_dir) / "data"

    if not force_clean:
        print("Clean extraction is disabled (force_clean=False). To force, set force_clean=True.")
        return

    # Verify: compare local file size to remote content-length header
    with requests.head(url, allow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        remote_size = int(r.headers.get("content-length", 0))

    local_size = archive.stat().st_size if archive.exists() else 0
    print(f"remote_size = {remote_size:,}")
    print(f"local_size  = {local_size:,}")

    if not archive.exists():
        raise FileNotFoundError(f"{archive_name} not found. Re-download it first.")

    if remote_size and local_size != remote_size:
        raise RuntimeError(
            "Local archive size does not match the server size. "
            "The download is incomplete or corrupted; delete it and re-download."
        )

    # Clean up any partial outputs from previous failed extraction attempts
    if partial_tar.exists():
        partial_tar.unlink()

    if data_dir.exists():
        shutil.rmtree(data_dir)

    # Stream-extract .zst directly into tarfile (memory-efficient)
    dctx = zstd.ZstdDecompressor()

    with open(archive, "rb") as compressed:
        with dctx.stream_reader(compressed) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                tar.extractall(path=output_dir)

    print("Done.")