import { INDUSTRIES, UNSET_INDUSTRY } from '@/lib/industries';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

const NONE = 'none';

export function IndustrySelect({
  value,
  onValueChange,
  emptyLabel = 'No industry',
}: {
  value: string;
  onValueChange: (value: string) => void;
  emptyLabel?: string;
}) {
  return (
    <Select
      value={value || NONE}
      onValueChange={(next) => onValueChange(next === NONE ? '' : next)}
    >
      <SelectTrigger>
        <SelectValue placeholder={emptyLabel} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>{emptyLabel}</SelectItem>
        {INDUSTRIES.map((industry) => (
          <SelectItem key={industry} value={industry}>
            {industry}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

const ALL_INDUSTRIES = 'all';

/** Contact-list filter. '' is every industry; UNSET_INDUSTRY is companies left blank. */
export function IndustryFilter({
  value,
  onValueChange,
}: {
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <Select
      value={value || ALL_INDUSTRIES}
      onValueChange={(next) => onValueChange(next === ALL_INDUSTRIES ? '' : next)}
    >
      <SelectTrigger className="w-72" aria-label="Filter contacts by industry">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_INDUSTRIES}>All industries</SelectItem>
        <SelectItem value={UNSET_INDUSTRY}>No industry</SelectItem>
        {INDUSTRIES.map((industry) => (
          <SelectItem key={industry} value={industry}>
            {industry}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
