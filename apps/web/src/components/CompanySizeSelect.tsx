import { COMPANY_SIZES } from '@/lib/company-sizes';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

const NONE = 'none';

export function CompanySizeSelect({
  value,
  onValueChange,
  emptyLabel = 'No size',
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
        {COMPANY_SIZES.map((size) => (
          <SelectItem key={size} value={size}>
            {size}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
