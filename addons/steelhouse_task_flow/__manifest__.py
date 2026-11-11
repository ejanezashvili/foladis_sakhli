{
    'name': 'Steelhouse Task Flow',
    'version': '19.0.1.44.0',
    'category': 'Services/Project',
    'summary': 'ფოლადის სახლი: სტადია-სტატუსი, მიზეზები, შემმოწმებელი, მტკიცებულება',
    'description': """
მოთხოვნები 3.1, 3.4-3.7, 3.9:
- სტადიას აქვს „ტიპი“ (ახალი, მიღებული, მიმდინარე, შეჩერებული, შემოწმებაზე, დაბრუნებული, დასრულებული, გაუქმებული)
- სტადიის შეცვლისას სტატუსი თავისით მიჰყვება და პირიქით
- შეჩერება / დაბრუნება / გაუქმება — მხოლოდ მიზეზით (შეჩერებისას + განახლების თარიღი)
- „შემმოწმებელი“: დასრულება, დაბრუნება და გაუქმება — მხოლოდ მას ან სისტემის ადმინისტრატორს
- „საჭიროა მტკიცებულება“: შემოწმებაზე ფაილის გარეშე ვერ გადავა
""",
    'author': 'Steelhouse',
    'license': 'LGPL-3',
    'depends': ['project', 'hr', 'steelhouse_hr'],
    'data': [
        'security/ir.model.access.csv',
        'security/project_rules.xml',
        'data/ir_cron.xml',
        'wizard/task_flow_wizard_views.xml',
        'views/project_task_type_views.xml',
        'views/project_task_views.xml',
        'views/all_tasks_views.xml',
        'views/task_template_views.xml',
        'views/task_final_views.xml',
        'views/project_project_views.xml',
        'data/ka_names.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'steelhouse_task_flow/static/src/sh_picker/*',
            'steelhouse_task_flow/static/src/stage_dialogs/*',
            'steelhouse_task_flow/static/src/task_steps/*',
        ],
    },
    'installable': True,
    'application': False,
}
