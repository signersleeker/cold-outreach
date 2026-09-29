import { INDUSTRIES } from '@/lib/industries';
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
