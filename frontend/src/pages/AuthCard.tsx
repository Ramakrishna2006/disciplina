import type { ReactNode } from "react"

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"

export function AuthCard({ title, description, children, footer }: {
  title: string
  description: string
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <div className="flex justify-center px-4 py-12 md:py-20">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-xl">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
        <CardFooter className="justify-center text-sm text-muted-foreground">{footer}</CardFooter>
      </Card>
    </div>
  )
}
