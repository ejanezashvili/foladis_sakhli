{
    'name': 'Steelhouse HR',
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'summary': 'ფოლადის სახლი: შემცვლელი, დეპარტამენტების იერარქია, შემცვლელები შვებულებისას',
    'author': 'Steelhouse',
    'license': 'LGPL-3',
    'depends': ['hr', 'hr_org_chart', 'web_hierarchy', 'hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_department_views.xml',
        'views/hr_department_hierarchy_views.xml',
        'views/hr_leave_views.xml',
    ],
    'assets': {
        'web.assets_backend_lazy': [
            'steelhouse_hr/static/src/department_hierarchy/*',
        ],
    },
    'installable': True,
    'application': False,
}
