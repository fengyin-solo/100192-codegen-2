/** 高风险作业票：列表页与详情页共用的许可状态、动作口径与接口封装。
 * 两个页面读的都是同一条后端记录、同一套 status，避免许可状态不一致。
 */
import { request } from '@/api/client'

export const ENDPOINT = '/api/workpermit'

export const CATEGORIES = [
  '动火作业',
  '登高作业',
  '受限空间作业',
  '吊装作业',
  '临时用电作业',
  '动土作业',
  '断路作业',
  '盲板抽堵作业',
]

export const STATUSES = ['待审签', '已审签', '作业中', '已关闭', '已驳回'] as const
export type PermitStatus = (typeof STATUSES)[number]

export const ACTIONS = {
  approve: '审签通过',
  reject: '审签驳回',
  enter: '进入现场',
  confirm: '监护确认',
  postpone: '申请延期',
  close: '关闭作业票',
} as const

export interface PostponeRecord {
  原有效期起: string
  原有效期止: string
  新有效期起: string
  新有效期止: string
  延期时间: string
  说明: string
}

export interface WorkpermitRow {
  id: number
  作业票编号: string
  作业类别: string
  作业地点: string
  监护人: string
  申请人: string
  作业内容: string
  有效期起: string
  有效期止: string
  登记时间: string
  status: PermitStatus
  许可状态: PermitStatus
  pending: boolean
  abnormal: boolean
  审签人: string
  审签结论: string
  审签时间: string
  审签说明: string
  监护人已确认: boolean
  监护确认时间: string
  关闭人: string
  关闭时间: string
  延期记录: PostponeRecord[]
}

/** 不同许可状态下允许的流转动作；不在列表里的按钮一律不展示。 */
export function actionsForStatus(status: PermitStatus): string[] {
  switch (status) {
    case '待审签':
      return [ACTIONS.approve, ACTIONS.reject]
    case '已审签':
      // 审签通过才能进现场；进场后才谈得上监护与关闭。
      return [ACTIONS.enter, ACTIONS.postpone]
    case '作业中':
      // 监护人没确认时关闭按钮也展示，但后端会拦下并给出说明。
      return [ACTIONS.confirm, ACTIONS.postpone, ACTIONS.close]
    case '已关闭':
    case '已驳回':
      return []
    default:
      return []
  }
}

export interface ActionParams {
  action: string
  审签人?: string
  说明?: string
  新有效期起?: string
  新有效期止?: string
  关闭人?: string
}

export interface ActionResponse {
  ok: boolean
  message: string
  entry: WorkpermitRow | null
}

export async function runPermitAction(id: number, params: ActionParams): Promise<ActionResponse> {
  const response = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
  if (!response.ok) {
    throw new Error('作业票动作未生效，请稍后重试')
  }
  return (await response.json()) as ActionResponse
}
