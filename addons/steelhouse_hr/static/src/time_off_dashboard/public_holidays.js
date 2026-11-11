import { patch } from "@web/core/utils/patch";
import { serializeDate } from "@web/core/l10n/dates";
import { TimeOffCalendarModel } from "@hr_holidays/views/calendar/calendar_model";
import { TimeOffCalendarYearRenderer } from "@hr_holidays/views/calendar/year/calendar_year_renderer";
import { TimeOffCalendarCommonRenderer } from "@hr_holidays/views/calendar/common/calendar_common_renderer";

// Public holidays get their own light green color in the time off calendar
// (Odoo greys them like weekends).
patch(TimeOffCalendarModel.prototype, {
    async updateData(data) {
        const prom = super.updateData(...arguments);
        const holidays = await this.orm.call(
            "hr.employee",
            "get_public_holidays_data",
            [serializeDate(data.range.start, "datetime"), serializeDate(data.range.end, "datetime")],
            { context: { employee_id: this.employeeId } }
        );
        const days = new Set();
        for (const holiday of holidays) {
            let day = luxon.DateTime.fromISO(holiday.start).startOf("day");
            const end = luxon.DateTime.fromISO(holiday.end);
            while (day <= end) {
                days.add(day.toISODate());
                day = day.plus({ days: 1 });
            }
        }
        data.shPublicHolidays = days;
        return prom;
    },
});

function holidayClass(renderer, info) {
    const days = renderer.props.model.data.shPublicHolidays;
    const date = luxon.DateTime.fromJSDate(info.date).toISODate();
    return days && days.has(date) ? ["o_sh_public_holiday"] : [];
}

patch(TimeOffCalendarYearRenderer.prototype, {
    getDayCellClassNames(info) {
        return [...super.getDayCellClassNames(info), ...holidayClass(this, info)];
    },
});

patch(TimeOffCalendarCommonRenderer.prototype, {
    getDayCellClassNames(info) {
        return [...super.getDayCellClassNames(info), ...holidayClass(this, info)];
    },
});
