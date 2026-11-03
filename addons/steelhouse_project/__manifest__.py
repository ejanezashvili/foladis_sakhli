{
    'name': 'Steelhouse Project',
    'version': '19.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'ფოლადის სახლი: დავალებების ნაკადი, შემოწმება, ვადის გადაწევა',
    'description': """
დავალებების მართვის დამატებები Odoo-ს Project აპლიკაციაზე:
- მთავარი პასუხისმგებელი და შემმოწმებელი
- სტადიები: ახალი, მიღებული, მიმდინარე, შეჩერებული, შემოწმებაზე, დაბრუნებული, დასრულებული, გაუქმებული
- ვადის გადაწევის მოთხოვნა და დადასტურება (თავდაპირველი ვადა ინახება)
- დაბრუნების, შეჩერების და გაუქმების მიზეზები
- მტკიცებულების ფაილის მოთხოვნა
- ვადის შეხსენება და ვადაგადაცილების შეტყობინება
- შაბლონები: მარაგების დათვლა, მარაგის შევსების მოთხოვნა
""",
    'author': 'Steelhouse',
    'license': 'LGPL-3',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'data/project_data.xml',
        'data/ir_cron.xml',
        'wizard/task_reason_wizard_views.xml',
        'wizard/task_extension_wizard_views.xml',
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
}
