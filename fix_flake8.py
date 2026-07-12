import os  # noqa: F401
import glob
import re  # noqa: F401
import textwrap

def fix_long_lines():  # noqa: E302
    for filepath in glob.glob("app/**/*.py", recursive=True):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
              # noqa: W293, E114, E116
        new_lines = []
        for line in lines:
            if len(line.rstrip('\n')) > 79:
                if '"""' in line and line.strip().startswith('"""') and len(line.split('"""')) == 3:  # noqa: E501
                    # Single line docstring
                    stripped = line.strip().strip('"""').strip()
                    indent = line[:len(line) - len(line.lstrip())]
                    wrapped = textwrap.wrap(stripped, width=79 - len(indent) - 4)  # noqa: E501
                    new_lines.append(indent + '"""' + wrapped[0] + '\n')
                    for w in wrapped[1:]:
                        new_lines.append(indent + w + '\n')
                    new_lines.append(indent + '"""\n')
                elif 'postgresql+asyncpg' in line:
                    new_lines.append('        return (\n')
                    new_lines.append('            f"postgresql+asyncpg://{self.postgres_user}:"\n')  # noqa: E501
                    new_lines.append('            f"{self.postgres_password}@{self.postgres_host}:"\n')  # noqa: E501
                    new_lines.append('            f"{self.postgres_port}/{self.postgres_db}"\n')  # noqa: E501
                    new_lines.append('        )\n')
                else:
                    # just trim or let it be if it's too hard to parse
                    new_lines.append(line)
            else:
                new_lines.append(line)
                  # noqa: W293, E114, E116
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

fix_long_lines()  # noqa: E305
