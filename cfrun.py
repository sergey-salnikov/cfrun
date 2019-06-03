import argparse
from collections import namedtuple
from pathlib import Path
import re
import subprocess
import sys
import time

from bs4 import BeautifulSoup
from requests import get

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

languages = dict(
    c=lambda src: [
        f"{src.with_suffix('')}",
        f"gcc --std=gnu11 -lm -o {src.with_suffix('')} {src}",
    ],
    cpp=lambda src: [
        f"{src.with_suffix('')}",
        f"g++ {src} -lm -o {src.with_suffix('')}",
    ],
    cs=lambda src: [
        f"{src.with_suffix('.exe')}",
        f"mcs {src}",
    ],
    d=lambda src: [
        f"{src.with_suffix('')}",
        f"dmd {src}",
    ],
    js='node',
    kt=lambda src: [
        f"java -jar {src.with_suffix('.jar')}",
        f"kotlinc {src} -include-runtime -d {src.with_suffix('.jar')}",
    ],
    pas=lambda src: [
        f"{src.with_suffix('')}",
        f"fpc {src}",
    ],
    php='php',
    py='python3',
    rb='ruby',
    scala=lambda src: [
        f"scala {src.with_suffix('')}",
        f"scalac {src}",
    ],
)

Test = namedtuple('Test', 'name input output')

def is_file_type_known(path):
    return Path(path).suffix[1:] in languages

def get_commands(source_path):
    commands = languages[Path(source_path).suffix[1:]]
    if callable(commands):
        return commands(Path(source_path))
    elif isinstance(commands, str):
        return (commands + ' ' + str(source_path), None)

def get_problem_url(source_path):
    full_path = str(Path(source_path).absolute())
    contest = re.findall(r'\d{2,}', full_path)[-1]
    problem = re.findall(r'[^A-Za-z][A-Za-z][0-9]?[^A-Za-z]', full_path)[-1][1:-1].upper()
    return f"https://codeforces.com/contest/{contest}/problem/{problem}"

def scrape_samples(url):
    soup = BeautifulSoup(get(url).content, features="html.parser")
    blocks = [div.pre.text.strip() for div in soup.find('div', 'sample-test')]
    return [Test(f"Пример {i+1}", blocks[2*i], blocks[2*i+1]) for i in range(0, len(blocks)//2)]

def save_tests(test_path, tests):
    with test_path.open('w') as test_file:
        for test in tests:
            test_file.write(f"### {test.name}\n{test.input}\n# вывод\n{test.output}\n\n")

def read_tests(test_path):
    try:
        tests = []
        name = input = output = ''
        with test_path.open() as test_file:
            for line in test_file:
                if line.startswith('### '):
                    if name:
                        tests.append(Test(name, input.strip(), output.strip()))
                    name = line[4:].strip()
                    in_output = False
                    input = output = ''
                elif line.startswith('# вывод'):
                    in_output = True
                elif name and not line.startswith('#'):
                    if in_output:
                        output += line
                    else:
                        input += line
            if name:
                tests.append(Test(name, input.strip(), output.strip()))
        return tests
    except FileNotFoundError:
        return None

def get_tests(source_path):
    test_path = Path(source_path).with_suffix('.test')
    tests = read_tests(test_path)
    if tests is None:
        url = get_problem_url(source_path)
        print(f"Скачиваю примеры с {url}")
        tests = scrape_samples(url)
        print(f"Ок, загрузил {len(tests)} примеров, записываю в {test_path}")
        save_tests(test_path, tests)
    else:
        print(f"Использую тесты из файла {test_path}")
    return tests

def run_tests(source_path):
    run_cmd, compile_cmd = get_commands(source_path)
    if compile_cmd:
        print(f"Компилирую: {compile_cmd}")
        sys.stdout.flush()
        if subprocess.run(compile_cmd.split()).returncode != 0:
            print(f"Ошибка компиляции ({compile_cmd})")
            return
    print(f"Запускаю: {run_cmd}")
    for test in get_tests(source_path):
        print(test.name, end=": ")
        sys.stdout.flush()
        result = subprocess.run(
            run_cmd.split(),
            input=test.input,
            stdout=subprocess.PIPE,
            encoding='utf-8',
            timeout=2,
        )
        output = result.stdout.strip()
        if output == test.output:
            print("OK")
        else:
            print("ответ не совпал")
            print("Ожидаемый ответ:")
            print(test.output)
            print("Полученный ответ:")
            print(output)
            break
    return True

def is_ignored(path):
    return path.name.startswith('.') or '#' in path.name

def handle_file_change(message, path):
    path = Path(path)
    if not path.is_absolute:
        path = path.relative_to('.')
    if not is_ignored(path) and is_file_type_known(path):
        print(f"{message} файл {path}")
        run_tests(path)

class Watcher(FileSystemEventHandler):
    def on_created(self, event):
        handle_file_change("Создан", event.src_path)

    def on_modified(self, event):
        handle_file_change("Изменён", event.src_path)

    def on_moved(self, event):
        handle_file_change("Переремещён", event.dest_path)

def watch(path):
    print(f"Слежу за изменениями в {path}")
    observer = Observer()
    observer.schedule(Watcher(), path=path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', nargs='?', default='.')
    argparser.add_argument('-w', '--watch', action='store_true')
    args = argparser.parse_args()
    if args.watch:
        watch(args.path)
    else:
        if is_file_type_known(args.path):
            run_tests(args.path)
        else:
            print(f"Не знаю, что делать с файлом такого типа: {args.path}")
