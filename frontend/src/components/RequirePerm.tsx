import { Result } from 'antd'
import type { ReactNode } from 'react'
import { useAuth } from '@/app/AuthContext'

export function RequirePerm({ perm, children }: { perm: string; children: ReactNode }) {
  const { can } = useAuth()
  if (!can(perm)) return <Result status="403" title="Not allowed" subTitle="Your role cannot open this page." />
  return <>{children}</>
}
