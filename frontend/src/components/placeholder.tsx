import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Stand-in for pages owned by feature modules. A module agent replaces the page
 * that renders this with the real implementation.
 */
export function Placeholder({
  title,
  description,
  owner,
}: {
  title: string;
  description: string;
  owner?: string;
}) {
  return (
    <div className="mx-auto w-full max-w-3xl py-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            This area is scaffolded and pending implementation
            {owner ? ` by the ${owner} module.` : "."}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
