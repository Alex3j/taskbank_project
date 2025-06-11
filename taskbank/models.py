from django.db import models

class ProgrammingLanguage(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name

class DifficultyLevel(models.Model):
    name = models.CharField(max_length=50)
    value = models.IntegerField()
    
    def __str__(self):
        return f"{self.name} ({self.value})"

class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название задачи")  # Явно указываем поле
    description = models.TextField(verbose_name="Описание")
    difficulty = models.ForeignKey('DifficultyLevel', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'taskbank_task'  # Явно задаём имя таблицы
        
    def __str__(self):
        return self.title

class Solution(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='solutions')
    language = models.ForeignKey(ProgrammingLanguage, on_delete=models.CASCADE)
    initial_code = models.TextField()
    correct_code = models.TextField()
    hint = models.TextField()
    
    def __str__(self):
        return f"{self.task.title} - {self.language.name}"
    
    def clean_code(self, code):
        """Нормализует код для сравнения"""
        return ''.join(code.split()).replace(' ', '')

