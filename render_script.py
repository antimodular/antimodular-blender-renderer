import bpy
import sys
import os
import re

# -------------------------------------
# Parse CLI arguments passed after '--'
# -------------------------------------
argv = sys.argv
if "--" in argv:
    idx = argv.index("--")
    args = argv[idx + 1 :]
else:
    args = []

# Defaults
output_dir = None
filename_prefix = "frame_"
resume = False
missing_frames = None  # New parameter for explicit list of frames to render

# Argument parser
i = 0
while i < len(args):
    if args[i] == "--output_dir":
        output_dir = args[i + 1]
        i += 2
    elif args[i] == "--prefix":
        filename_prefix = args[i + 1]
        i += 2
    elif args[i] == "--resume":
        resume = args[i + 1].lower() == "true"
        i += 2
    elif args[i] == "--missing_frames":  # Handle new parameter
        try:
            missing_frames = [int(f) for f in args[i + 1].split(",")]
            print(f"[INFO] Received list of {len(missing_frames)} specific frames to render")
        except Exception as e:
            print(f"[ERROR] Failed to parse missing frames: {e}")
        i += 2
    else:
        i += 1

# -------------------------------------
# Setup and validate output directory
# -------------------------------------
scene = bpy.context.scene

if not output_dir:
    # Use whatever was set in the .blend file
    output_dir = bpy.path.abspath(scene.render.filepath)

if not output_dir or output_dir.strip() == "":
    output_dir = "/tmp"

output_dir = os.path.abspath(output_dir)
os.makedirs(output_dir, exist_ok=True)

# -------------------------------------
# Frame range detection
# -------------------------------------
start_frame = scene.frame_start
end_frame = scene.frame_end

# -------------------------------------
# Resume logic
# -------------------------------------
# If we were provided with specific missing frames, use those
if missing_frames:
    print(f"[INFO] Will render {len(missing_frames)} specific frames")
    frames_to_render = sorted(missing_frames)
    
    # For progress reporting
    start_frame = min(frames_to_render)
    end_frame = max(frames_to_render)
else:
    # Original behavior - find highest rendered frame
    existing_files = [f for f in os.listdir(output_dir) if f.endswith(".png")]
    frame_pattern = re.compile(rf"{re.escape(filename_prefix)}(\d+)\.png")

    last_rendered = 0
    if resume:
        for f in existing_files:
            match = frame_pattern.match(f)
            if match:
                frame_num = int(match.group(1))
                last_rendered = max(last_rendered, frame_num)

        start_frame = max(start_frame, last_rendered + 1)
        
    # Regular sequential frames
    frames_to_render = list(range(start_frame, end_frame + 1))

if not frames_to_render:
    print(f"[INFO] All frames already rendered in {output_dir}")
    sys.exit(0)

# -------------------------------------
# Set render format
# -------------------------------------
scene.render.image_settings.file_format = "PNG"

# -------------------------------------
# Frame-by-frame rendering
# -------------------------------------
print(f"[INFO] Starting render: {len(frames_to_render)} frames to render")
print(f"[INFO] Output path: {output_dir}")
print(f"[INFO] Filename prefix: {filename_prefix}")
print(f"[INFO] Resume enabled: {resume}")

for frame in frames_to_render:
    padded = str(frame).zfill(5)
    output_filename = f"{filename_prefix}{padded}.png"
    full_output_path = os.path.join(output_dir, output_filename)

    if os.path.exists(full_output_path):
        print(f"[SKIP] Frame {frame} already exists, skipping...")
        continue

    scene.frame_set(frame)
    scene.render.filepath = os.path.join(output_dir, f"{filename_prefix}{padded}")

    print(f"[RENDER] Frame {frame}/{end_frame} → {full_output_path}")

    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print(f"[ERROR] Rendering failed at frame {frame}: {e}")
        sys.exit(1)

print(f"[DONE] Rendering completed.")
