from django.contrib import admin
from .models import ProgrammingLanguage, DifficultyLevel, Task, Solution

class SolutionInline(admin.TabularInline):
    model = Solution
    extra = 1

@admin.register(ProgrammingLanguage)
class ProgrammingLanguageAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(DifficultyLevel)
class DifficultyLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'value')
    ordering = ('value',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'created_at')
    list_filter = ('difficulty',)
    inlines = [SolutionInline]

@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ('task', 'language', 'short_hint')
    
    def short_hint(self, obj):
        return obj.hint[:50] + '...' if len(obj.hint) > 50 else obj.hint
    short_hint.short_description = 'Hint'

