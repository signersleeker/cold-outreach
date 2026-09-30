import { useCancelFollowUp, useContactFollowUp } from '@/hooks';
import { formatDate, formatDateTime } from '@/lib/format';
import { ErrorBanner } from './AppLayout';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardBody, CardHeader, CardTitle } from './ui/card';
import { Skeleton } from './ui/skeleton';

export function ContactFollowUpCard({
  contactId,
  onSendStep,
}: {
  contactId: string;
  onSendStep?: (templateId: string) => void;
}) {
  const { data: plan, isLoading } = useContactFollowUp(contactId);
  const cancel = useCancelFollowUp();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Follow-up plan</CardTitle>
        </CardHeader>
        <CardBody>
          <Skeleton className="h-16 w-full" />
        </CardBody>
      </Card>
    );
  }

  if (!plan) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Follow-up plan</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-muted-foreground">
            No active plan. Assign a template group from Send to track the sequence here.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{plan.groupName}</CardTitle>
        <Button
          size="sm"
          variant="ghost"
          className="text-danger"
          disabled={cancel.isPending}
          onClick={() => cancel.mutate(contactId)}
        >
          Cancel plan
        </Button>
      </CardHeader>
      <CardBody className="space-y-2">
        <ol className="space-y-1.5">
          {plan.steps.map((step) => {
            const isNext =
              plan.nextStep?.id === step.id && step.status === 'pending' && step.dueOn !== null;
            return (
              <li
                key={step.id}
                className="flex items-start gap-2 rounded-[var(--radius-sm)] border px-2.5 py-2"
              >
                <span className="w-5 font-mono text-xs text-muted-foreground">
                  {step.position + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{step.templateName}</p>
                  <p className="text-xs text-muted-foreground">
                    {step.status === 'sent'
                      ? `Sent ${formatDateTime(step.sentAt)}`
                      : step.dueOn
                        ? `Due ${formatDate(step.dueOn)}`
                        : 'Waiting on the previous email'}
                    {step.position > 0 && step.status === 'pending'
                      ? ` · ${step.delayDays}d after previous`
                      : null}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge
                    tone={
                      step.status === 'sent'
                        ? 'success'
                        : isNext
                          ? 'warning'
                          : step.status === 'cancelled'
                            ? 'muted'
                            : 'muted'
                    }
                  >
                    {step.status === 'sent'
                      ? 'sent'
                      : isNext
                        ? 'due'
                        : step.dueOn
                          ? 'scheduled'
                          : 'waiting'}
                  </Badge>
                  {isNext && onSendStep ? (
                    <Button size="sm" variant="outline" onClick={() => onSendStep(step.templateId)}>
                      Send
                    </Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
        <ErrorBanner error={cancel.error} />
      </CardBody>
    </Card>
  );
}
