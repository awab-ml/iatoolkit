# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.tasks_repo import TaskRepo
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Task, TaskType, Company, TaskStatus
from iatoolkit.repositories.database_manager import DatabaseManager


class TestTaskRepo:
    def setup_method(self):
        self.db_manager = DatabaseManager('sqlite:///:memory:')
        self.db_manager.create_all()
        self.session = self.db_manager.get_session()
        self.profile_repo = ProfileRepo(self.db_manager)


        self.company = Company(name='opensoft', short_name='open')
        self.profile_repo.create_company(self.company)

        self.task_type = TaskType(name="dummy_type")
        self.task = Task(id=1, task_type_id=1, company_id=self.company.id)

        self.repo = TaskRepo(self.db_manager)


    def test_create_task(self):
        result = self.repo.create_task(self.task)

        task_in_db = self.session.query(Task).filter_by(id=self.task.id).first()

        assert task_in_db is not None
        assert task_in_db.id == self.task.id
        assert task_in_db.task_type_id == self.task.task_type_id
        assert task_in_db.company_id == self.task.company_id
        assert result == task_in_db

    def test_update_task(self):
        self.repo.create_task(self.task)

        # update value
        self.task.client_data = {'key': 'value'}
        result = self.repo.update_task(self.task)

        task_in_db = self.session.query(Task).filter_by(id=self.task.id).first()
        assert task_in_db.client_data == self.task.client_data

    def test_create_or_update_task_type_creates_new(self):
        result = self.repo.create_or_update_task_type(self.task_type)
        assert result == self.task_type

    def test_create_or_update_task_type_updates_existing(self):
        existing_type = TaskType(name="dummy_type", prompt_template="old_template", template_args="old_args")
        self.repo.create_or_update_task_type(existing_type)


        new_type = TaskType(name="dummy_type", prompt_template="new_template", template_args="new_args")
        result = self.repo.create_or_update_task_type(new_type)

        assert existing_type.prompt_template == "new_template"
        assert existing_type.template_args == "new_args"
        assert result == existing_type

    def test_get_task_type_when_found(self):
        result = self.repo.get_task_type("dummy_type")
        assert result == None

    def test_get_pending_tasks(self):
        self.task.status = TaskStatus.pendiente
        self.repo.create_task(self.task)

        result = self.repo.get_pending_tasks(self.company.id)
        assert len(result) == 1

