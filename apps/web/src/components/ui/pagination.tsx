import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './button';

/** Shared by Contacts, Companies and Company detail, which each had their own copy. */
export function Pagination({
  offset,
  pageSize,
  total,
  onOffsetChange,
}: {
  offset: number;
  pageSize: number;
  total: number;
  onOffsetChange: (offset: number) => void;
}) {
  if (total <= pageSize) return null;

  return (
    <div className="flex items-center justify-between gap-3 text-xs">
      <span className="font-mono tabular-nums text-muted-foreground">
        {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
      </span>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
        >
          <ChevronLeft />
          Previous
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={offset + pageSize >= total}
          onClick={() => onOffsetChange(offset + pageSize)}
        >
          Next
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
