import argparse
from collections import namedtuple
from pathlib import Path
import re
import subprocess
import sys
import time

import browser_cookie3
from bs4 import BeautifulSoup
from requests import get
import requests_cache

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

APP_NAME = 'cfrun'
CACHE_PATH = Path.home() / '.cache' / APP_NAME

languages = dict(
    c=lambda src: [
        f"{src.with_suffix('')}",
        f"gcc --std=gnu11 -lm -o {src.with_suffix('')} {src}",
    ],
    cpp=lambda src: [
        f"{src.with_suffix('')}",
        f"g++ --std=gnu++17 {src} -lm -o {src.with_suffix('')}",
    ],
    cs=lambda src: [
        f"{src.with_suffix('.exe')}",
        f"mcs {src}",
    ],
    d=lambda src: [
        f"{src.with_suffix('')}",
        f"dmd {src}",
    ],
    jl='julia',
    hs=lambda src: [
        f"{src.with_suffix('')}",
        f"ghc {src}",
    ],
    java=lambda src: [
        f"java {src.with_suffix('')}",
        f"javac {src}",
    ],
    js='node',
    kt=lambda src: [
        f"java -jar {src.with_suffix('.jar')}",
        f"kotlinc {src} -include-runtime -d {src.with_suffix('.jar')}",
    ],
    ml=lambda src: [
        f"{src.with_suffix('')}",
        f"ocamlopt -w -8 nums.cmxa str.cmxa -o {src.with_suffix('')} {src}",
    ],
    pas=lambda src: [
        f"{src.with_suffix('')}",
        f"fpc {src}",
    ],
    php='php',
    pl='perl',
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
    problem = re.findall(r'[^A-Za-z][A-Za-z][0-9]?[^A-Za-z]', full_path)[-1][1:-1].upper()
    try:
        dot_contest = Path(source_path).parent / '.contest'
        contest_url = dot_contest.open().read().strip()
    except:
        contest = re.findall(r'\d{2,}', full_path)[-1]
        contest_url = f"https://codeforces.com/contest/{contest}/problem/%s/"
    return contest_url % (problem,)

def scrape_samples(url):
    requests_cache.install_cache(str(CACHE_PATH))
    cookies = browser_cookie3.firefox()
    soup = BeautifulSoup(get(url, cookies=cookies).content, features="html.parser")
    blocks = list(soup.find_all('pre'))
    inputs = ["\n".join(div.text for div in block.find_all('div')) for block in blocks[::2]]
    outputs = [block.text.strip() for block in blocks[1::2]]
    return [Test(f"Пример {i+1}", inputs[i], outputs[i]) for i in range(len(inputs))]

def get_tests(source_path):
    try:
        url = get_problem_url(source_path)
    except:
        print("Не установил соответствие с контестом/задачей")
        return None
    print(f"Скачиваю примеры с {url}")
    try:
        tests = scrape_samples(url)
    except:
        print("Не сумел загрузить примеры")
        return None
    print(f"Ок, загрузил {len(tests)} примеров")
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
    tests = get_tests(source_path)
    if tests:
        for test in tests:
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
    else:
        subprocess.run(run_cmd.split())
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
