import os
import subprocess
import shutil
from pathlib import Path

# --- CONFIGURATION ---
INPUT_FOLDER = "/data/media/karaoke/songs"
OUTPUT_FOLDER = "/data/media/karaoke/songs_normalized"
TARGET_LUFS = -14        # Standard volume level for web/streaming
EXTENSIONS = {".mp4", ".mkv", ".mov"} # File types to look for

def normalize_videos():
    # 1. Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"Created output folder: {OUTPUT_FOLDER}")

    # 2. Get list of all video files
    # We use Path() because it handles OS paths (Windows vs Mac) automatically
    files = [f for f in os.listdir(INPUT_FOLDER) if Path(f).suffix.lower() in EXTENSIONS]

    if not files:
        print(f"No video files found in '{INPUT_FOLDER}'!")
        return

    print(f"Found {len(files)} videos to process.\n")

    # 3. Loop through videos and process
    for index, filename in enumerate(files):
        input_path = os.path.join(INPUT_FOLDER, filename)
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        
        print(f"[{index+1}/{len(files)}] Processing: {filename}...")

        # Construct the FFmpeg command
        # We pass the command as a LIST of strings. This is safer and 
        # handles filenames with spaces (common in Karaoke) automatically.
        command = [
            "ffmpeg",
            "-y",                     # Overwrite output file without asking
            "-i", input_path,         # Input file
            "-c:v", "copy",           # Copy video stream (NO re-encoding)
            "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11", # Audio Filter
            output_path               # Output file
        ]

        try:
            # Run the command and hide the massive wall of text FFmpeg usually spits out
            # capture_output=True keeps your terminal clean.
            subprocess.run(command, check=True, capture_output=True)
            print("   -> Done!")
            
        except subprocess.CalledProcessError as e:
            print(f"   -> ERROR processing {filename}.")
            # Print the specific error from FFmpeg if it fails
            print(f"   Error details: {e.stderr.decode()}")

    print("\nAll tasks finished.")

if __name__ == "__main__":
    normalize_videos()