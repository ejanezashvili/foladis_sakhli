from odoo import api, fields, models

# Proposed department codes (requirement 6.5); editable on the department (project) form
DEFAULT_CODES = {
    'Call ცენტრის გაყიდვები': 'CALL',
    'ადმინისტრაცია': 'ADM',
    'ადმინისტრაცია / ოფის მენეჯერი': 'ADM-OFF',
    'ბადეების საწარმო': 'BAD',
    'ბადეების საწარმო / კომერციული მიმართულება': 'BAD-COM',
    'ბადეების საწარმო / წარმოება': 'BAD-PRD',
    'ბადეების საწარმო / წარმოება / ოპერატორი': 'BAD-OPR',
    'ბალასტი': 'BAL',
    'ბრენდმენეჯმენტის განყოფილება': 'BRD',
    'ბრენდმენეჯმენტის განყოფილება / ბრენდ მენეჯერები': 'BRD-MNG',
    'გაყიდვების განყოფილება': 'SAL',
    'იურიდიული დეპარტამენტი': 'LEG',
    'იურიდიული დეპარტამენტი / გარე იურისტი': 'LEG-EXT',
    'იურიდიული დეპარტამენტი / შიდა იურისტი': 'LEG-INT',
    'იჯარები': 'RNT',
    'კვადრატულების საწარმო': 'KVD',
    'კვადრატულების საწარმო / ბრენდის განყოფილება': 'KVD-BRD',
    'კვადრატულების საწარმო / კომერციული მიმართულება': 'KVD-COM',
    'კვადრატულების საწარმო / წარმოება': 'KVD-PRD',
    'კვადრატულების საწარმო / წარმოება / მზა პროდუქციის საწყობი': 'KVD-FGW',
    'კვადრატულების საწარმო / წარმოება / საწარმოო საწყობი': 'KVD-PWH',
    'ლოჯისტიკა': 'LOG',
    'ლოჯისტიკა / ლოჯისტიკის კურატორი': 'LOG-CUR',
    'ლოჯისტიკა / ლოჯისტიკის კურატორი / ავტოპარკი': 'LOG-AVT',
    'ლოჯისტიკა / ფილიალის ხელმძღვანელი': 'LOG-BRM',
    'ლოჯისტიკა / ფილიალის ხელმძღვანელი / საცალო გაყიდვები და სერვისი': 'LOG-RTL',
    'ლოჯისტიკა / ფილიალის ხელმძღვანელი / საწყობი და ინვენტარიზაცია': 'LOG-WH',
    'ლოჯისტიკა / ფილიალის ხელმძღვანელი / საწყობი და ინვენტარიზაცია / საწყობის მენეჯერი': 'LOG-WHM',
    'მარკეტინგი': 'MKT',
    'ნადირულის მეურნეობა': 'NAD',
    'პროექტების განვითარების განყოფილება': 'DEV',
    'საბაჟო': 'CUS',
    'საქფაქტორი': 'SKF',
    'სახურავების საწარმო': 'ROF',
    'სახურავების საწარმო / კომერციული მიმართულება': 'ROF-COM',
    'სახურავების საწარმო / წარმოება': 'ROF-PRD',
    'სახურავების საწარმო / წარმოება / ოპერატორი': 'ROF-OPR',
    'ტენდერების გაყიდვები': 'TND',
    'ფინანსების დეპარტამენტი': 'FIN',
    'ფინანსების დეპარტამენტი / ანალიტიკა': 'FIN-ANL',
    'ფინანსების დეპარტამენტი / ბუღალტერია': 'FIN-ACC',
    'ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები': 'FIN-CHA',
    'ქონსტრაქშენის ცეხი': 'CON',
    'ქონსტრაქშენის ცეხი / ბრენდის განყოფილება': 'CON-BRD',
    'ქონსტრაქშენის ცეხი / კომერციული მიმართულება': 'CON-COM',
    'ქონსტრაქშენის ცეხი / წარმოება': 'CON-PRD',
    'ქონსტრაქშენის ცეხი / წარმოება / კარ-ფანჯარა': 'CON-WIN',
    'ქონსტრაქშენის ცეხი / წარმოება / რკინა': 'CON-IRN',
}


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sh_code = fields.Char('დავალებების კოდი', help="დავალების ნომრის დასაწყისი, მაგ. ADM → ADM-0012.")
    sh_number_next = fields.Integer('შემდეგი ნომერი', default=1, copy=False)

    def _sh_take_number(self):
        """Next number of this department, safe for parallel use."""
        self.ensure_one()
        self.env.cr.execute(
            "UPDATE project_project SET sh_number_next = COALESCE(sh_number_next, 1) + 1 "
            "WHERE id = %s RETURNING sh_number_next - 1", [self.id])
        self.invalidate_recordset(['sh_number_next'])
        return self.env.cr.fetchone()[0]


class ProjectTask(models.Model):
    _inherit = 'project.task'
    _rec_names_search = ['name', 'sh_number']

    sh_number = fields.Char('ნომერი', copy=False, readonly=True, index=True)

    def _sh_assign_number(self):
        for task in self.filtered(lambda t: not t.sh_number and not t.is_template and t.project_id):
            if task.parent_id:
                parent = task.parent_id
                if not parent.sh_number:
                    parent._sh_assign_number()
                if parent.sh_number:
                    siblings = parent.with_context(active_test=False).child_ids.filtered('sh_number')
                    n = len(siblings) + 1
                    while f'{parent.sh_number}/{n}' in siblings.mapped('sh_number'):
                        n += 1
                    task.sh_number = f'{parent.sh_number}/{n}'
                continue
            code = task.project_id.sh_code
            if code:
                task.sh_number = '%s-%04d' % (code, task.project_id._sh_take_number())

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks.with_context(sh_no_log=True)._sh_assign_number()
        return tasks

    @api.model
    def _sh_init_numbers(self):
        """Codes for the departments + numbers for existing tasks (by creation date)."""
        Project = self.env['project.project'].with_context(active_test=False)
        for project in Project.search([('sh_is_department', '=', True), ('sh_code', '=', False)]):
            code = DEFAULT_CODES.get(project.with_context(lang='ka_GE').name)
            if code:
                project.sh_code = code
        tasks = self.with_context(active_test=False).search(
            [('sh_number', '=', False), ('is_template', '=', False), ('project_id', '!=', False)],
            order='create_date, id')
        tasks.filtered(lambda t: not t.parent_id).with_context(sh_no_log=True)._sh_assign_number()
        tasks.filtered('parent_id').with_context(sh_no_log=True)._sh_assign_number()
