import os
import glob

def check_context_usage():
    files = glob.glob('/Users/neo/.openclaw/workspace/memory/*.md')
    total_size = 0

    for file in files:
        total_size += os.path.getsize(file)

    return total_size

if __name__ == '__main__':
    usage = check_context_usage()
    print(f'Total context usage: {usage} bytes')
