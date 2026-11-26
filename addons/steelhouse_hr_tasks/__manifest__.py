{
    'name': 'Steelhouse: კადრების პროცესები',
    'version': '19.0.1.20.0',
    'summary': 'ვაკანსია, ახალი თანამშრომლის აყვანა, გათავისუფლება - დავალებებად, დირექტორის დამტკიცებით',
    'description': """
HR-ის სამი პროცესი (კომპანიის დოკუმენტები, 2026-11-25) დავალებებად: სავალდებულო ველები, HR-ის შემოწმება,
დირექტორის დამტკიცება / უარყოფა, დამტკიცების შემდეგ იურიდიული პირის ბუღალტერი და იურისტი + ქვედავალებები.
ადამიანები და იურიდიული პირები - „კადრები → პარამეტრები“. steelhouse_task_flow-ის ფაილებს არ ცვლის (D-10).
""",
    'author': 'ფოლადის სახლი',
    'license': 'LGPL-3',
    'depends': ['steelhouse_task_flow', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_task_data.xml',
        'wizard/hr_refuse_wizard_views.xml',
        'views/hr_task_config_views.xml',
        'views/task_hr_process_views.xml',
    ],
    'assets': {'web.assets_backend': ['steelhouse_hr_tasks/static/src/hr_tasks.scss']},
    'post_init_hook': '_sh_hr_tasks_post_init',
    'installable': True,
    'application': True,
}
