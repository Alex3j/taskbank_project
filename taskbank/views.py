from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
from .models import Task, Solution, ProgrammingLanguage
import json
import tempfile
import subprocess
import os
import re
import platform
from django.conf import settings

def index(request):
    tasks = Task.objects.all() 
    languages = ProgrammingLanguage.objects.all()
    return render(request, 'taskbank/index.html', {
        'tasks': tasks,
        'languages': languages
    })

def get_attempt_data(request, task_id, language_id):
    """Получает или создает данные о попытках"""
    session_key = f"attempts_{task_id}_{language_id}"
    default_data = {
        'attempts_left': 3,
        'is_blocked': False,
        'block_until': None
    }
    
    attempt_data = request.session.get(session_key, default_data.copy())
    
    # Проверяем блокировку
    if attempt_data['is_blocked'] and attempt_data['block_until']:
        block_until = timezone.datetime.fromisoformat(attempt_data['block_until'])
        if timezone.now() < block_until:
            return attempt_data, True, (block_until - timezone.now()).seconds
        else:
            # Разблокируем если время вышло
            attempt_data.update(default_data)
    
    return attempt_data, False, 0

def task_detail(request, task_id, language_id):
    task = get_object_or_404(Task, pk=task_id)
    language = get_object_or_404(ProgrammingLanguage, pk=language_id)
    solution = get_object_or_404(Solution, task=task, language=language)
    
    attempt_data, is_blocked, time_left = get_attempt_data(request, task_id, language_id)
    
    if is_blocked:
        return render(request, 'taskbank/task_blocked.html', {
            'task': task,
            'language': language,
            'time_left': time_left
        })
    
    return render(request, 'taskbank/task_detail.html', {
        'task': task,
        'language': language,
        'solution': solution,
        'attempts_left': attempt_data['attempts_left'],
        'is_blocked': is_blocked,
        'block_time': time_left,
        'csrf_token': request.COOKIES.get('csrftoken', '')
    })

def check_code_execution(language_id, code, timeout=5):
    """Проверяет, что код компилируется и запускается без ошибок"""
    is_windows = platform.system() == 'Windows'
    
    commands = {
        1: {"compile": None, "run": ["python", "{file}"]},  # Python
        3: {"compile": ["g++", "{file}", "-o", "{exe}"],    # C++
            "run": ["./{exe}"] if not is_windows else ["{exe}.exe"]},
        2: {"compile": ["javac", "{file}"],                 # Java
            "run": ["java", "{class_name}"]}
    }
    
    lang_config = commands.get(language_id)
    if not lang_config:
        return False, "Unsupported language"
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            ext = {1: '.py', 3: '.cpp', 2: '.java'}[language_id]
            file_name = "Solution" + ext
            file_path = os.path.join(temp_dir, file_name)
            class_name = "Solution"
            
            # Обработка Java: выделяем импорты и создаем правильную структуру
            if language_id == 2:
                # Извлекаем все импорты
                imports = []
                other_lines = []
                
                for line in code.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("import ") or stripped.startswith("package "):
                        imports.append(line)
                    else:
                        other_lines.append(line)
                
                other_code = "\n".join(other_lines)
                
                # Проверяем наличие класса
                if "class " not in other_code:
                    # Создаем полный класс с методом main
                    wrapped_code = f"""
{"\n".join(imports)}

public class Solution {{
    // Пользовательский код
    {other_code}
    
    public static void main(String[] args) {{
        // Точка входа
        // Для проверки можно добавить тестовые вызовы функций
    }}
}}"""
                    code = wrapped_code
                else:
                    # Если класс уже есть, добавляем метод main внутрь класса
                    if "public static void main" not in other_code:
                        # Находим закрывающую скобку класса
                        last_brace_index = other_code.rfind('}')
                        if last_brace_index != -1:
                            # Вставляем main перед закрывающей скобкой класса
                            main_method = "\n    public static void main(String[] args) {}\n"
                            other_code = other_code[:last_brace_index] + main_method + other_code[last_brace_index:]
                    
                    # импорты + основной код
                    code = "\n".join(imports) + "\n\n" + other_code
            
            # Обработка C++: добавляем минимальный main
            elif language_id == 3:
                if "main(" not in code and "main (" not in code:
                    code += "\n\nint main() { return 0; }"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Компилируем код
            if lang_config["compile"]:
                compile_cmd = [
                    c.format(file=file_path, exe="solution", class_name=class_name) 
                    for c in lang_config["compile"]
                ]
                
                compile_proc = subprocess.run(
                    compile_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=temp_dir,
                    timeout=timeout,
                    shell=is_windows
                )
                
                if compile_proc.returncode != 0:
                    error_msg = compile_proc.stderr.decode('utf-8', errors='ignore')
                    return False, error_msg
            
            # Формируем команду для запуска
            if language_id == 2:
                run_cmd = ["java", "-cp", temp_dir, class_name]
            else:
                run_cmd = [
                    c.format(file=file_path, exe="solution", class_name=class_name) 
                    for c in lang_config["run"]
                ]
            
            # Запускаем код
            run_proc = subprocess.run(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temp_dir,
                timeout=timeout,
                shell=is_windows
            )
            
            # Проверяем результат выполнения
            if run_proc.returncode != 0:
                error_msg = run_proc.stderr.decode('utf-8', errors='ignore')
                return False, error_msg
            
            return True, None
    
    except subprocess.TimeoutExpired:
        return False, "Execution timed out"
    except Exception as e:
        return False, str(e)

@require_http_methods(["POST"])
def submit_solution(request, task_id, language_id):
    task = get_object_or_404(Task, pk=task_id)
    language = get_object_or_404(ProgrammingLanguage, pk=language_id)
    solution = get_object_or_404(Solution, task=task, language=language)
    
    try:
        data = json.loads(request.body)
        user_code = data.get('code', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    
    # Проверка минимальной длины кода
    if len(user_code) < 5:
        return JsonResponse({'status': 'error', 'message': 'Code must be at least 5 characters long'}, status=400)
    
    attempt_data, is_blocked, time_left = get_attempt_data(request, task_id, language_id)
    session_key = f"attempts_{task_id}_{language_id}"
    
    if is_blocked:
        return JsonResponse({
            'status': 'blocked',
            'time_left': time_left
        })
    
    # Этап 1: Проверка что код запускается
    runs_successfully, error = check_code_execution(language_id, user_code)
    
    if not runs_successfully:
        # Уменьшаем счетчик попыток
        attempt_data['attempts_left'] -= 1
        response = {
            'status': 'incorrect',
            'attempts_left': attempt_data['attempts_left'],
            'message': f'Code execution failed: {error}'
        }
        
        if attempt_data['attempts_left'] <= 0:
            # Блокируем после 3 неудачных попыток
            attempt_data['is_blocked'] = True
            attempt_data['block_until'] = str(timezone.now() + timedelta(seconds=10))
            response = {
                'status': 'blocked',
                'time_left': 10,
                'hint': solution.hint
            }
        
        # Сохраняем данные в сессии
        request.session[session_key] = attempt_data
        request.session.modified = True
        return JsonResponse(response)
    
    # Этап 2: Сравнение с эталонным решением
    normalized_user_code = solution.clean_code(user_code)
    normalized_solution = solution.clean_code(solution.correct_code)
    is_correct = normalized_user_code == normalized_solution
    
    response = {}
    
    if is_correct:
        # Сбрасываем счетчик попыток при правильном ответе
        attempt_data.update({
            'attempts_left': 3,
            'is_blocked': False,
            'block_until': None
        })
        response = {
            'status': 'correct',
            'message': 'Correct solution!',
            'attempts_left': attempt_data['attempts_left']
        }
    else:
        # Уменьшаем счетчик попыток
        attempt_data['attempts_left'] -= 1
        response = {
            'status': 'incorrect',
            'attempts_left': attempt_data['attempts_left'],
            'message': 'Solution does not match reference implementation'
        }
        
        if attempt_data['attempts_left'] <= 0:
            # Блокируем после 3 неудачных попыток
            attempt_data['is_blocked'] = True
            attempt_data['block_until'] = str(timezone.now() + timedelta(seconds=10))
            response = {
                'status': 'blocked',
                'time_left': 10,
                'hint': solution.hint
            }
    
    # Сохраняем данные в сессии
    request.session[session_key] = attempt_data
    request.session.modified = True
    
    return JsonResponse(response)
