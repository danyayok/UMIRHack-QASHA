import asyncio
from app.db.session import AsyncSessionLocal
from app.models import Project, Analysis, User
from app.utils.security import get_password_hash


async def create_test_data():
    """Создает тестовые данные для разработки"""
    async with AsyncSessionLocal() as db:
        # Создаем тестового пользователя
        user = await db.execute(
            "SELECT * FROM users WHERE email = 'test@example.com'"
        )
        user = user.first()

        if not user:
            user = User(
                email="test@example.com",
                hashed_password=get_password_hash("test123"),
                full_name="Test User"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print("✅ Test user created")

        # Создаем тестовые проекты
        test_projects = [
            {
                "name": "Python API Project",
                "description": "Пример Python FastAPI приложения",
                "repo_url": "https://github.com/fastapi/fastapi",
                "technology_stack": ["python", "fastapi"],
                "owner_id": user.id
            },
            {
                "name": "React Frontend",
                "description": "React приложение с тестами",
                "repo_url": "https://github.com/facebook/react",
                "technology_stack": ["javascript", "react"],
                "owner_id": user.id
            },
            {
                "name": "ZIP Project",
                "description": "Проект из ZIP архива",
                "repo_url": None,
                "technology_stack": ["python"],
                "owner_id": user.id
            }
        ]

        for project_data in test_projects:
            existing = await db.execute(
                "SELECT * FROM projects WHERE name = :name AND owner_id = :owner_id",
                {"name": project_data["name"], "owner_id": user.id}
            )
            if not existing.first():
                project = Project(**project_data)
                db.add(project)
                await db.commit()
                await db.refresh(project)

                # Добавляем тестовый анализ
                analysis = Analysis(
                    project_id=project.id,
                    status="completed",
                    result={
                        "technologies": project_data["technology_stack"],
                        "metrics": {
                            "total_files": 42,
                            "test_files": 8,
                            "code_files": 34
                        },
                        "file_structure": {
                            "main.py": {"technology": "python", "is_test": False, "size": 1024},
                            "test_main.py": {"technology": "python", "is_test": True, "size": 512}
                        }
                    },
                    generated_tests={
                        "total_generated": 5,
                        "test_files": ["test_main.py", "test_api.py"],
                        "frameworks_used": ["pytest"]
                    }
                )
                db.add(analysis)
                await db.commit()
                print(f"✅ Project '{project.name}' created")

        print("🎉 Test data setup completed!")


if __name__ == "__main__":
    asyncio.run(create_test_data())