<template>
  <section class="page" data-module="permit">
    <header class="page-head">
      <div>
        <h2>高风险作业票台账</h2>
        <p class="page-desc">登记动火、登高等高风险作业票，把申请、审签、监护到关闭串成一条许可流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记作业票</button>
        <button class="btn" type="button" @click="exportRows">导出作业票台账</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>票号</span>
        <input v-model="filters.keyword" placeholder="按票号检索" />
      </label>
      <label class="filter-item">
        <span>作业类别</span>
        <select v-model="filters.category">
          <option value="">全部类别</option>
          <option v-for="item in categories" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>许可状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
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
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无高风险作业票数据，可先登记作业票</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条作业票记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
    </footer>

    <div v-if="showCreate" class="dialog-mask" @click.self="showCreate = false">
      <form class="dialog" @submit.prevent="submitCreate">
        <h3>登记高风险作业票</h3>
        <label v-for="field in createFields" :key="field.key" class="dialog-item">
          <span>{{ field.label }}<em v-if="field.required">*</em></span>
          <select v-if="field.key === '作业类别'" v-model="createForm[field.key]">
            <option v-for="item in categories" :key="item" :value="item">{{ item }}</option>
          </select>
          <input
            v-else
            v-model="createForm[field.key]"
            :type="field.key === '有效期至' ? 'date' : 'text'"
            :placeholder="`请填写${field.label}`"
          />
        </label>
        <p class="dialog-tip">作业类别、作业地点、监护人为必填；登记后进入待审签，审签通过才能进现场。</p>
        <div class="dialog-actions">
          <button class="btn primary" type="submit">提交登记</button>
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
        </div>
      </form>
    </div>

    <div v-if="detail" class="dialog-mask" @click.self="detail = null">
      <div class="dialog">
        <h3>作业票详情 · {{ detail['票号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] ?? '—' }}</dd>
          </template>
          <dt>审签记录</dt>
          <dd>{{ approveLog }}</dd>
        </dl>
        <div class="dialog-actions">
          <button class="btn ghost" type="button" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/permit'
const columns = ["票号", "作业类别", "作业地点", "申请人", "监护人", "有效期至", "监护确认", "许可状态"]
const actions = ["提交审签", "开始作业", "办理延期", "监护确认", "关闭作业票"]
const statuses = ["待审签", "已审签", "作业中", "已关闭"]
const categories = ["动火作业", "登高作业", "受限空间作业", "临时用电作业", "吊装作业"]
const createFields = [
  { key: "票号", label: "票号", required: true },
  { key: "作业类别", label: "作业类别", required: true },
  { key: "作业地点", label: "作业地点", required: true },
  { key: "申请人", label: "申请人", required: false },
  { key: "作业单位", label: "作业单位", required: false },
  { key: "监护人", label: "监护人", required: true },
  { key: "有效期至", label: "有效期至", required: false },
]
const detailFields = ["票号", "作业类别", "作业地点", "申请人", "作业单位", "监护人", "有效期至", "监护确认", "许可状态"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', category: '', status: '' })
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const detail = ref<Row | null>(null)

const stats = computed(() => [
  { label: '待审签', value: rows.value.filter((row) => row['许可状态'] === '待审签').length },
  { label: '作业中', value: rows.value.filter((row) => row['许可状态'] === '作业中').length },
  { label: '已关闭', value: rows.value.filter((row) => row['许可状态'] === '已关闭').length },
])

const approveLog = computed(() => {
  const log = detail.value?.['审签记录']
  if (!Array.isArray(log) || !log.length) {
    return '暂无审签记录'
  }
  return log.map((item) => `${item['审签人'] ?? '—'}：${item['结果'] ?? '—'}`).join('；')
})

function resetFilters() {
  filters.value = { keyword: '', category: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {
    票号: `PERM-${String(total.value + 1).padStart(4, '0')}`,
    作业类别: categories[0],
    作业地点: '',
    申请人: '',
    作业单位: '',
    监护人: '',
    有效期至: '',
  }
  showCreate.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '作业票登记未生效，请检查必填字段')
    }
    showCreate.value = false
    noticeMessage.value = payload.message ?? '作业票已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业票登记失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('作业票详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业票详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, string> = { action }
  if (action === '办理延期') {
    const due = window.prompt(`当前有效期至 ${row['有效期至'] ?? '—'}，请输入新的有效期（YYYY-MM-DD）`)
    if (!due) {
      return
    }
    values['有效期至'] = due
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '作业票动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? `作业票已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业票操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.category) query.set('category', filters.value.category)
  if (filters.value.status) query.set('status', filters.value.status)
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('作业票列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业票列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.dialog {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-width: 90vw;
}
.dialog h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.dialog-item {
  display: block;
  margin-bottom: 10px;
}
.dialog-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.dialog-item em {
  color: #b42318;
  font-style: normal;
}
.dialog-item input,
.dialog-item select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.dialog-tip {
  font-size: 12px;
  color: var(--muted);
}
.dialog-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.ok-text {
  color: #067647;
}
select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  background: #fff;
}
</style>
