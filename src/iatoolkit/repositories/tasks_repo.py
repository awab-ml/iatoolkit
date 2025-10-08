# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from injector import inject
from datetime import datetime
from iatoolkit.repositories.models import Task, TaskStatus, TaskType
from iatoolkit.repositories.database_manager import DatabaseManager
from sqlalchemy import or_


class TaskRepo:
    @inject
    def __init__(self, db_manager: DatabaseManager):
        self.session = db_manager.get_session()

    def create_task(self, new_task: Task) -> Task:
        self.session.add(new_task)
        self.session.commit()
        return new_task

    def update_task(self, task: Task) -> Task:
        self.session.commit()
        return task

    def get_task_by_id(self, task_id: int):
        return self.session.query(Task).filter_by(id=task_id).first()

    def create_or_update_task_type(self, new_task_type: TaskType):
        task_type = self.session.query(TaskType).filter_by(name=new_task_type.name).first()
        if task_type:
            task_type.prompt_template = new_task_type.prompt_template
            task_type.template_args = new_task_type.template_args
        else:
            self.session.add(new_task_type)
            task_type = new_task_type
        self.session.commit()
        return task_type

    def get_task_type(self, name: str):
        task_type = self.session.query(TaskType).filter_by(name=name).first()
        return task_type

    def get_pending_tasks(self, company_id: int):
        now = datetime.now()
        tasks = self.session.query(Task).filter(
            Task.company_id == company_id,
            Task.status == TaskStatus.pendiente,
            or_(Task.execute_at == None, Task.execute_at <= now)
        ).all()
        return tasks
