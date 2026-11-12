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

const SH_MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი",
    "ივლისი", "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
const SH_WEEKDAYS = ["კვ", "ორ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ"]; // Date.getDay(): 0 = Sunday

patch(TimeOffCalendarYearRenderer.prototype, {
    // Georgian month titles ("იანვარი 2026") and weekday labels, whatever the browser locale
    get options() {
        return {
            ...super.options,
            titleFormat: (info) => `${SH_MONTHS[info.date.month]} ${info.date.year}`,
            dayHeaderContent: (arg) => SH_WEEKDAYS[arg.date.getDay()],
        };
    },

    getDayCellClassNames(info) {
        return [...super.getDayCellClassNames(info), ...holidayClass(this, info)];
    },
});

patch(TimeOffCalendarCommonRenderer.prototype, {
    getDayCellClassNames(info) {
        return [...super.getDayCellClassNames(info), ...holidayClass(this, info)];
    },
});
