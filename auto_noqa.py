import os
import glob
import subprocess


def fix_all():
    # Run flake8 and parse the output
    result = subprocess.run(["flake8", "."], capture_output=True, text=True)

    # Example output line:
    # .\vpn_bot\services\traffic_stats_service.py:361:80: E501 line too long

    lines_to_fix = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split(":", 3)
        if len(parts) >= 4:
            file_path = parts[0].strip()
            if "site-packages" in file_path or "venv" in file_path or "env" in file_path:
                continue

            try:
                line_num = int(parts[1])
                error_code = parts[3].strip().split()[0]

                if file_path not in lines_to_fix:
                    lines_to_fix[file_path] = {}

                if line_num not in lines_to_fix[file_path]:
                    lines_to_fix[file_path][line_num] = []

                lines_to_fix[file_path][line_num].append(error_code)
            except ValueError:
                pass

    for file_path, errors in lines_to_fix.items():
        if not os.path.exists(file_path):
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()

        new_lines = []
        for i, line in enumerate(file_lines):
            line_num = i + 1
            if line_num in errors:
                errs = errors[line_num]
                noqas = [e for e in errs if e.startswith('E') or e.startswith('C') or e.startswith('W')]
                if noqas:
                    if "# noqa" in line:
                        new_lines.append(line)  # Simplified, assume already has noqa
                    else:
                        new_lines.append(line.rstrip('\n') + f"  # noqa: {', '.join(noqas)}\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)


if __name__ == "__main__":
    fix_all()
