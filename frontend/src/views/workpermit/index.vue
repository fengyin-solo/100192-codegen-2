<template>
  <section class="page" data-module="workpermit">
    <header class="page-head">
      <div>
        <h2>高风险作业票台账</h2>
        <p class="page-desc">把作业许可从申请、审签、监护到关闭串成一条状态流转；动火、登高等作业必须审签通过才能进现场。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记作业票</button>
        <button class="btn" type="button" @click="exportRows">导出台账</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value" :class="item.emphasis ? 'stat-hot' : ''">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="filters.keyword" placeholder="按票编号 / 地点 / 监护人检索" />
      </label>
      <label class="filter-item">
        <span>作业类别</span>
        <select v-model="filters.category">
          <option value="">全部类别</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>许可状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" class="clickable" @click="openDetail(row.id)">
          <td>{{ row['作业票编号'] }}</td>
          <td>{{ row['作业类别'] }}</td>
          <td>{{ row['作业地点'] }}</td>
          <td>{{ row['监护人'] }}</td>
          <td>{{ row['申请人'] || '—' }}</td>
          <td>{{ row['有效期起'] }} 至 {{ row['有效期止'] }}</td>
          <td><span class="status-badge" :data-status="row['许可状态']">{{ row['许可状态'] }}</span></td>
          <td class="row-actions" @click.stop>
            <button
              v-for="action in actionsForStatus(row.status)"
              :key="action"
              class="link"
              type="button"
              @click="runRowAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无高风险作业票，可先登记一张动火或登高作业票</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 张作业票</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>

    <!-- 登记作业票 -->
    <div v-if="creating" class="modal-mask" @click.self="creating = false">
      <form class="modal" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记高风险作业票</h3>
        <div class="modal-grid">
          <label class="form-item">
            <span>作业类别 *</span>
            <select v-model="form['作业类别']">
              <option value="" disabled>请选择动火 / 登高等类别</option>
              <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>作业票编号</span>
            <input v-model="form['作业票编号']" placeholder="留空自动生成 HWP-xxxx" />
          </label>
          <label class="form-item">
            <span>作业地点 *</span>
            <input v-model="form['作业地点']" placeholder="如：一号升压站开关柜室" />
          </label>
          <label class="form-item">
            <span>监护人 *</span>
            <input v-model="form['监护人']" placeholder="现场监护人姓名" />
          </label>
          <label class="form-item">
            <span>申请人</span>
            <input v-model="form['申请人']" placeholder="默认当前值班人员" />
          </label>
          <label class="form-item">
            <span>作业内容</span>
            <input v-model="form['作业内容']" placeholder="简述本次高风险作业内容" />
          </label>
          <label class="form-item">
            <span>有效期起 *</span>
            <input v-model="form['有效期起']" type="date" />
          </label>
          <label class="form-item">
            <span>有效期止 *</span>
            <input v-model="form['有效期止']" type="date" />
          </label>
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="creating = false">取消</button>
          <button class="btn primary" type="submit">提交登记</button>
        </div>
      </form>
    </div>

    <!-- 延期 -->
    <div v-if="postponeTarget" class="modal-mask" @click.self="postponeTarget = null">
      <form class="modal" @submit.prevent="submitPostpone">
        <h3 class="modal-title">延期 {{ postponeTarget['作业票编号'] }}</h3>
        <p class="page-desc">当前有效期：{{ postponeTarget['有效期起'] }} 至 {{ postponeTarget['有效期止'] }}，延期将切换到新的有效期。</p>
        <div class="modal-grid">
          <label class="form-item">
            <span>新有效期起 *</span>
            <input v-model="postponeForm['新有效期起']" type="date" />
          </label>
          <label class="form-item">
            <span>新有效期止 *</span>
            <input v-model="postponeForm['新有效期止']" type="date" />
          </label>
          <label class="form-item form-wide">
            <span>延期说明</span>
            <input v-model="postponeForm['说明']" placeholder="如：作业量超出预估，需顺延" />
          </label>
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="postponeTarget = null">取消</button>
          <button class="btn primary" type="submit">确认延期</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import {
  ACTIONS,
  CATEGORIES,
  ENDPOINT,
  STATUSES,
  actionsForStatus,
  runPermitAction,
  type ActionParams,
  type WorkpermitRow,
} from './useWorkpermit'

const router = useRouter()

const columns = ['作业票编号', '作业类别', '作业地点', '监护人', '申请人', '有效期', '许可状态']
const categories = CATEGORIES
const statuses = STATUSES

const rows = ref<WorkpermitRow[]>([])
const total = ref(0)
const counts = ref<Record<string, number>>({ 待审签: 0, 已审签: 0, 作业中: 0, 已关闭: 0, 已驳回: 0 })
const filters = reactive({ keyword: '', category: '', status: '' })

const message = ref('')
const messageOk = ref(false)

const statCards = computed(() => [
  { label: '待审签', value: counts.value['待审签'] ?? 0, emphasis: true },
  { label: '已审签', value: counts.value['已审签'] ?? 0, emphasis: false },
  { label: '作业中', value: counts.value['作业中'] ?? 0, emphasis: false },
  { label: '待关闭（监护已确认）', value: guardianConfirmedCount.value, emphasis: false },
  { label: '已关闭', value: counts.value['已关闭'] ?? 0, emphasis: false },
])

const guardianConfirmedCount = computed(
  () => rows.value.filter((row) => row.status === '作业中' && row['监护人已确认']).length,
)

const creating = ref(false)
const formError = ref('')
const emptyForm = {
  作业类别: '',
  作业票编号: '',
  作业地点: '',
  监护人: '',
  申请人: '',
  作业内容: '',
  有效期起: '',
  有效期止: '',
}
const form = reactive({ ...emptyForm })

const postponeTarget = ref<WorkpermitRow | null>(null)
const postponeForm = reactive({ 新有效期起: '', 新有效期止: '', 说明: '' })

function flash(text: string, ok = false) {
  message.value = text
  messageOk.value = ok
}

function resetFilters() {
  filters.keyword = ''
  filters.category = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openDetail(id: number) {
  void router.push({ name: 'workpermit-detail', params: { id } })
}

function openCreate() {
  Object.assign(form, emptyForm)
  formError.value = ''
  creating.value = true
}

async function submitCreate() {
  formError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      formError.value = payload.message || '登记失败'
      return
    }
    creating.value = false
    flash(payload.message || '作业票已登记', true)
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '登记失败'
  }
}

async function runRowAction(action: string, row: WorkpermitRow) {
  // 延期需要填写新有效期，走弹窗；其余动作直接确认后提交。
  if (action === ACTIONS.postpone) {
    postponeTarget.value = row
    postponeForm['新有效期起'] = row['有效期起']
    postponeForm['新有效期止'] = row['有效期止']
    postponeForm['说明'] = ''
    formError.value = ''
    return
  }
  const params: ActionParams = { action }
  if (action === ACTIONS.reject) {
    const reason = window.prompt('请填写驳回原因（安全条件不满足的具体项）')
    if (reason === null) return
    params['说明'] = reason
  }
  if (!window.confirm(`确认对作业票 ${row['作业票编号']} 执行「${action}」？`)) return
  try {
    const result = await runPermitAction(row.id, params)
    flash(result.message, result.ok)
    await reload()
  } catch (error) {
    flash(error instanceof Error ? error.message : '操作失败', false)
  }
}

async function submitPostpone() {
  if (!postponeTarget.value) return
  formError.value = ''
  try {
    const result = await runPermitAction(postponeTarget.value.id, {
      action: ACTIONS.postpone,
      ...postponeForm,
    })
    if (!result.ok) {
      formError.value = result.message
      return
    }
    postponeTarget.value = null
    flash(result.message, true)
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '延期失败'
  }
}

async function reload() {
  message.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (filters.category) query.set('category', filters.category)
  if (filters.status) query.set('status', filters.status)
  try {
    const [listRes, statsRes] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listRes.ok) throw new Error('作业票列表读取失败')
    const payload = await listRes.json()
    rows.value = (payload.items ?? []) as WorkpermitRow[]
    total.value = payload.total ?? rows.value.length
    if (statsRes.ok) {
      const stats = await statsRes.json()
      counts.value = stats
    }
  } catch (error) {
    flash(error instanceof Error ? error.message : '作业票列表读取失败', false)
  }
}

onMounted(reload)
</script>
