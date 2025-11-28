import os
import sys
import re

def read_last_n_lines(file_path, n):
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Go to the end of the file
            f.seek(0, os.SEEK_END)
            total_bytes = f.tell()
            f.seek(0) # Go back to beginning

            # Iterate backwards through file
            # This is a more robust way to read last N lines without loading entire file for very large files
            # or relying on specific OS commands
            buffer_size = 4096
            bytes_read = 0
            while bytes_read < total_bytes and len(lines) < n:
                bytes_to_read = min(buffer_size, total_bytes - bytes_read)
                f.seek(total_bytes - bytes_read - bytes_to_read)
                buffer = f.read(bytes_to_read)
                
                # Split buffer by lines and add to the beginning of lines list
                # This handles cases where a newline might be at the end of a buffer segment
                current_lines = buffer.splitlines(True)
                lines = current_lines + lines
                
                bytes_read += bytes_to_read
            
            # Ensure we only return the last N lines if more were read
            return ''.join(lines[-n:])
    except FileNotFoundError:
        return f"Error: File not found at {file_path}"
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

def search_log_for_pattern(file_path, pattern, context_lines_after=0):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            results = []
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    results.append(line)
                    for j in range(1, context_lines_after + 1):
                        if i + j < len(lines):
                            results.append(lines[i+j])
            return ''.join(results)
    except FileNotFoundError:
        return f"Error: File not found at {file_path}"
    except Exception as e:
        return f"Error searching file {file_path}: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python read_logs_helper.py <mode> <file_path> <arg1> [arg2]")
        sys.exit(1)
    
    mode = sys.argv[1]
    file_path = sys.argv[2]

    if mode == "last_lines":
        num_lines = int(sys.argv[3])
        print(read_last_n_lines(file_path, num_lines))
    elif mode == "search_pattern":
        pattern = sys.argv[3]
        context_lines_after = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        print(search_log_for_pattern(file_path, pattern, context_lines_after))
    else:
        print(f"Unknown mode: {mode}. Use 'last_lines' or 'search_pattern'.")
        sys.exit(1)