// 7.10: the report screens print the same rows as their Excel file to a PDF (models/task_pdf.py).
// "lines": the Excel rows - the first row is the header, an empty row starts a new table (its first
// row is that table's header). In the first table a row with an empty 2nd cell is a group / total
// row (bold); the rows under it are its items (the repeated group name is left out).
export function linesToSections(lines) {
    const sections = [];
    let current = null;
    for (const line of lines) {
        if (!line.length) {
            current = null;
            continue;
        }
        const cells = line.map((v) => (v === null || v === undefined ? "" : String(v)));
        if (!current) {
            current = { head: cells, rows: [] };
            sections.push(current);
            continue;
        }
        if (sections.length === 1 && cells.length > 1) {
            const group = cells[1] === "";
            if (!group) {
                cells[0] = "";
            }
            current.rows.push({ cells, bold: group, sub: !group });
        } else {
            current.rows.push({ cells, bold: false, sub: false });
        }
    }
    return sections;
}

export async function downloadTablePdf(orm, action, title, subtitle, lines) {
    const report = await orm.call("project.task", "sh_table_pdf", [
        { title, subtitle, sections: linesToSections(lines) },
    ]);
    await action.doAction(report);
}
