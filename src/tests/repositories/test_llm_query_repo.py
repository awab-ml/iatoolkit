# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.repositories.database_manager import DatabaseManager
from iatoolkit.repositories.models import LLMQuery, Function, Company, Prompt, PromptCategory
from iatoolkit.repositories.llm_query_repo import LLMQueryRepo
from datetime import datetime, timedelta


class TestLLMQueryRepo:
    def setup_method(self):
        self.db_manager = DatabaseManager('sqlite:///:memory:')
        self.db_manager.create_all()
        self.session = self.db_manager.get_session()
        self.repo = LLMQueryRepo(self.db_manager)
        self.query = LLMQuery(id=1, company_id=2,
                              user_identifier='user_1',
                              query="test query",
                              output='an output',
                              response={'answer': 'an answer'},
                              answer_time=3)
        self.function = Function(name="function1",
                                company_id=1,
                                description="A description",
                                parameters={'name': 'value'})
        self.company = Company(name='test_company',
                               short_name='test')
        self.session.add(self.company)
        self.session.commit()


    def test_add_query_when_success(self):
        new_query = self.repo.add_query(self.query)
        assert new_query.id == 1

    def test_get_company_functions_when_ok(self):
        self.function.company_id = self.company.id

        self.session.add(self.function)
        self.session.commit()
        assert len(self.repo.get_company_functions(self.company)) == 1

    def test_create_or_update_function_when_new_function(self):
        new_function = Function(name="function1",
                                company_id=1,
                                description="A description",
                                parameters={'name': 'value'})
        result = self.repo.create_or_update_function(new_function=new_function)
        assert result.id is not None
        assert result.name == "function1"
        assert result.description == "A description"

    def test_create_or_update_function_when_updating_function(self):
        # Add an initial function
        function = Function(name="function1",
                                company_id=self.company.id,
                                description="A description",
                                parameters={'name': 'value'})
        self.session.add(function)
        self.session.commit()

        # Update the description
        upd_function = Function(name="function1",
                            company_id=self.company.id,
                            description="New description",
                            parameters={'name': 'value 2'})
        result = self.repo.create_or_update_function(new_function=upd_function)
        assert result.id == function.id
        assert result.description == "New description"
        assert result.parameters['name'] == 'value 2'

    def test_create_or_update_prompt_when_new_prompt(self):
        new_prompt = Prompt(name="prompt1",
                                company_id=self.company.id,
                                description="an intelligent prompt",
                                filename='')
        result = self.repo.create_or_update_prompt(new_prompt=new_prompt)
        assert result.id is not None
        assert result.name == "prompt1"
        assert result.description == "an intelligent prompt"
        assert result.active is True

    def test_create_or_update_prompt_when_updating_prompt(self):

        category = self.repo.create_or_update_prompt_category(PromptCategory(name='Cobranzas', order=6,
                             company_id=self.company.id))
        prompt = Prompt(name="prompt1",
                        company_id=self.company.id,
                        category_id=category.id,
                        active=True,
                        order=1,
                        description="an intelligent prompt",
                        filename='')
        self.session.add(prompt)
        self.session.commit()

        # Update the description
        upd_prompt = Prompt(name="prompt1",
                            company_id=self.company.id,
                            category_id=category.id,
                            active=True,
                            order=3,
                            description="a super intelligent prompt",
                            filename='')
        result = self.repo.create_or_update_prompt(new_prompt=upd_prompt)
        assert result.description == "a super intelligent prompt"
        assert result.id == prompt.id

    def test_get_history_empty_result(self):
        """Test get_history when no queries exist for the user"""
        # Get history for non-existent user
        history = self.repo.get_history(self.company, 'nonexistent_user')

        # Should return empty list
        assert len(history) == 0
        assert history == []

    def test_get_history_different_company(self):
        """Test get_history filters by company_id correctly"""
        # Add two companies
        company1 = Company(name='company1', short_name='comp1')
        company2 = Company(name='company2', short_name='comp2')
        self.session.add(company1)
        self.session.add(company2)
        self.session.commit()

        # Create queries for different companies
        query1 = LLMQuery(
            company_id=company1.id,
            user_identifier='user123',
            query="Company 1 query",
            output='Company 1 output',
            response={'answer': 'Company 1 answer'},
            answer_time=3
        )
        query2 = LLMQuery(
            company_id=company2.id,
            user_identifier='user123',
            query="Company 2 query",
            output='Company 2 output',
            response={'answer': 'Company 2 answer'},
            answer_time=3
        )

        # Add queries to database
        self.session.add(query1)
        self.session.add(query2)
        self.session.commit()

        # Get history for company1
        history1 = self.repo.get_history(company1, 'user123')
        assert len(history1) == 1
        assert history1[0].query == "Company 1 query"

        # Get history for company2
        history2 = self.repo.get_history(company2, 'user123')
        assert len(history2) == 1
        assert history2[0].query == "Company 2 query"

    def test_get_history_limit_100(self):
        """Test get_history respects the limit of 100 queries"""
        # Create 110 queries
        queries = []
        base_time = datetime(2024, 1, 15, 10, 30, 0)
        for i in range(110):
            # Use timedelta to create unique timestamps
            query = LLMQuery(
                company_id=self.company.id,
                user_identifier='user123',
                query=f"Query {i}",
                output=f'Output {i}',
                response={'answer': f'Answer {i}'},
                answer_time=3,
                created_at=base_time + timedelta(seconds=i)  # Different timestamps
            )
            queries.append(query)

        # Add all queries to database
        for query in queries:
            self.session.add(query)
        self.session.commit()

        # Get history
        history = self.repo.get_history(self.company, 'user123')

        # Should return only 100 queries (limit)
        assert len(history) == 100
        # Should be ordered by created_at desc (newest first)
        assert history[0].query == "Query 109"  # Newest
        assert history[99].query == "Query 10"   # 100th newest

    def test_get_history_mixed_user_types(self):
        """Test get_history correctly filters by user type"""
        # Create queries for different user types
        external_query = LLMQuery(
            company_id=self.company.id,
            user_identifier='external_user',
            query="External user query",
            output='External output',
            response={'answer': 'External answer'},
            answer_time=3
        )
        local_query = LLMQuery(
            company_id=self.company.id,
            user_identifier='user_456',
            query="Local user query",
            output='Local output',
            response={'answer': 'Local answer'},
            answer_time=3
        )

        # Add queries to database
        self.session.add(external_query)
        self.session.add(local_query)
        self.session.commit()

        # Get history for external user
        external_history = self.repo.get_history(self.company, 'external_user')
        assert len(external_history) == 1
        assert external_history[0].query == "External user query"

        # Get history for local user
        local_history = self.repo.get_history(self.company, 'user_456')
        assert len(local_history) == 1
        assert local_history[0].query == "Local user query"

    def test_get_history_ordering(self):
        """Test get_history orders by created_at desc correctly"""

        # Create queries with different timestamps
        old_query = LLMQuery(
            company_id=self.company.id,
            user_identifier='user123',
            query="Old query",
            output='Old output',
            response={'answer': 'Old answer'},
            answer_time=3,
            created_at=datetime(2024, 1, 15, 10, 30, 0)
        )
        new_query = LLMQuery(
            company_id=self.company.id,
            user_identifier='user123',
            query="New query",
            output='New output',
            response={'answer': 'New answer'},
            answer_time=3,
            created_at=datetime(2024, 1, 15, 11, 30, 0)
        )

        # Add queries to database
        self.session.add(old_query)
        self.session.add(new_query)
        self.session.commit()

        # Get history
        history = self.repo.get_history(self.company, 'user123')

        # Should be ordered by created_at desc (newest first)
        assert len(history) == 2
        assert history[0].query == "New query"  # Newest first
        assert history[1].query == "Old query"  # Oldest last

    def test_get_history_no_company_queries(self):
        """Test get_history when company exists but has no queries"""

        # Get history for company with no queries
        history = self.repo.get_history(self.company, 'user123')

        # Should return empty list
        assert len(history) == 0
        assert history == []

    def test_get_prompts_when_prompts_exist(self):
        """Test get_prompts returns all prompts for a company."""
        # Create active and inactive prompts for the same company
        prompt1 = Prompt(name="active_prompt",
                         company_id=self.company.id,
                         description="An active prompt",
                         active=True,
                         filename='')
        prompt2 = Prompt(name="inactive_prompt",
                         company_id=self.company.id,
                         description="An inactive prompt",
                         active=False,
                         filename='')

        self.session.add_all([prompt1, prompt2])
        self.session.commit()

        # Get prompts for the company
        prompts = self.repo.get_prompts(self.company)

        # Should return both prompts
        assert len(prompts) == 2
        prompt_names = {p.name for p in prompts}
        assert "active_prompt" in prompt_names
        assert "inactive_prompt" in prompt_names

    def test_get_prompts_when_no_prompts_exist(self):
        """Test get_prompts returns an empty list when a company has no prompts."""
        # Get prompts for a company with no prompts
        prompts = self.repo.get_prompts(self.company)

        # Should return an empty list
        assert len(prompts) == 0
        assert prompts == []

    def test_get_prompts_filters_by_company(self):
        """Test get_prompts only returns prompts for the specified company."""
        # Create another company
        other_company = Company(name='other_company', short_name='other')
        self.session.add(other_company)
        self.session.commit()

        # Create a prompt for the main company
        prompt1 = Prompt(name="main_company_prompt",
                         company_id=self.company.id,
                         description="Prompt for the main company",
                         filename='')

        # Create a prompt for the other company
        prompt2 = Prompt(name="other_company_prompt",
                         company_id=other_company.id,
                         description="Prompt for the other company",
                         filename='')

        self.session.add_all([prompt1, prompt2])
        self.session.commit()

        # Get prompts for the main company
        prompts = self.repo.get_prompts(self.company)

        # Should only return the prompt for the main company
        assert len(prompts) == 1
        assert prompts[0].name == "main_company_prompt"
        assert prompts[0].company_id == self.company.id


