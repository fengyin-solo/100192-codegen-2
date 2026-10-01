<template>
  <section class="page" data-module="workpermit-detail" v-if="entry">
    <header class="page-head">
      <div>
        <h2>
          作业票 {{ entry['作业票编号'] }}
          <span class="status-badge" :data-status="entry['许可状态']">{{ entry['许可状态'] }}</span>
        </h2>
        <p class="page-desc">{{ entry['作业类别'] }} · {{ entry['作业地点'] }} · 监护人：{{ entry['监护人'] }}</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn ghost" :to="{ name: 'workpermit' }">返回台账列表</RouterLink>
      </div>
    </header>

    <div class="detail-grid">
      <article class="detail-card">
        <h3 class="card-title">登记信息</h3>
        <dl class="detail-list">
          <dt>作业类别</dt><dd>{{ entry['作业类别'] }}</dd>
          <dt>作业地点</dt><dd>{{ entry['作业地点'] }}</dd>
          <dt>作业内容</dt><dd>{{ entry['作业内容'] || '—' }}</dd>
          <dt>申请人</dt><dd>{{ entry['申请人'] || '—' }}</dd>
          <dt>登记时间</dt><dd>{{ entry['登记时间'] || '—' }}</dd>
        </dl>
      </article>

      <article class="detail-card">
        <h3 class="card-title">许可有效期</h3>
        <dl class="detail-list">
          <dt>当前有效期</dt><dd>{{ entry['有效期起'] }} 至 {{ entry['有效期止'] }}</dd>
          <dt>许可状态</dt>
          <dd><span class="status-badge" :data-status="entry['许可状态']">{{ entry['许可状态'] }}</span></dd>
          <dt>延期次数</dt><dd>{{ entry['延期记录']?.length ?? 0 }} 次</dd>
        </dl>
      </article>

      <article class="detail-card">
        <h3 class="card-title">审签记录</h3>
        <dl class="detail-list">
          <dt>审签结论</dt><dd>{{ entry['审签结论'] || '尚未审签' }}</dd>
          <dt>审签人</dt><dd>{{ entry['审签人'] || '—' }}</dd>
          <dt>审签时间</dt><dd>{{ entry['审签时间'] || '—' }}</dd>
          <dt>审签说明</dt><dd>{{ entry['审签说明'] || '—' }}</dd>
        </dl>
        <p v-if="entry.status === '已驳回'" class="error-text">该票已驳回终止，审签结果只保留一次，不能进入现场。</p>
      </article>

      <article class="detail-card">
        <h3 class="card-title">监护与关闭</h3>
        <dl class="detail-list">
          <dt>监护人</dt><dd>{{ entry['监护人'] }}</dd>
          <dt>监护确认</dt>
          <dd>
            <span :class="entry['监护人已确认'] ? 'ok-text' : 'muted-text'">
              {{ entry['监护人已确认'] ? `已于 ${entry['监护确认时间']} 确认` : '尚未确认' }}
            </span>
          </dd>
          <dt>关闭人</dt><dd>{{ entry['关闭人'] || '—' }}</dd>
          <dt>关闭时间</dt><dd>{{ entry['关闭时间'] || '—' }}</dd>
        </dl>
      </article>
    </div>

    <article class="detail-card" v-if="entry['延期记录']?.length">
      <h3 class="card-title">延期记录</h3>
      <table class="data-table">
        <thead>
          <tr><th>延期时间</th><th>原有效期</th><th>新有效期</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="(record, index) in entry['延期记录']" :key="index">
            <td>{{ record['延期时间'] }}</td>
            <td>{{ record['原有效期起'] }} 至 {{ record['原有效期止'] }}</td>
            <td>{{ record['新有效期起'] }} 至 {{ record['新有效期止'] }}</td>
            <td>{{ record['说明'] }}</td>
          </tr>
        </tbody>
      </table>
    </article>

    <div class="action-bar">
      <button
        v-for="action in availableActions"
        :key="action"
        class="btn"
        :class="action === ACTIONS.approve ? 'primary' : ''"
        type="button"
        @click="runDetailAction(action)"
      >
        {{ action }}
      </button>
      <span v-if="!availableActions.length" class="muted-text">
        {{ entry.status === '已关闭' ? '作业票已关闭，关闭之后不能再变更。' : '该票已终止，无可用动作。' }}
      </span>
    </div>

    <footer class="page-foot">
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>

    <!-- 延期弹窗与列表页保持同一套口径 -->
    <div v-if="postponing" class="modal-mask" @click.self="postponing = false">
      <form class="modal" @submit.prevent="submitPostpone">
        <h3 class="modal-title">申请延期</h3>
        <p class="page-desc">当前有效期：{{ entry['有效期起'] }} 至 {{ entry['有效期止'] }}</p>
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
            <input v-model="postponeForm['说明']" placeholder="延期原因" />
          </label>
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="postponing = false">取消</button>
          <button class="btn primary" type="submit">确认延期</button>
        </div>
      </form>
    </div>
  </section>

  <section v-else class="page">
    <p class="error-text">{{ loadError || '作业票读取中…' }}</p>
    <RouterLink class="btn" :to="{ name: 'workpermit' }">返回台账列表</RouterLink>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchJson } from '@/api/client'
import {
  ACTIONS,
  ENDPOINT,
  actionsForStatus,
  runPermitAction,
  type ActionParams,
  type WorkpermitRow,
} from './useWorkpermit'

const route = useRoute()
const entryId = Number(route.params.id)

const entry = ref<WorkpermitRow | null>(null)
const loadError = ref('')
const message = ref('')
const messageOk = ref(false)
const postponing = ref(false)
const formError = ref('')
const postponeForm = reactive({ 新有效期起: '', 新有效期止: '', 说明: '' })

// 与列表页共用 actionsForStatus：两个页面可执行动作、许可状态完全一致。
const availableActions = computed(() =>
  entry.value ? actionsForStatus(entry.value.status) : [],
)

async function load() {
  loadError.value = ''
  try {
    entry.value = await fetchJson<WorkpermitRow>(`${ENDPOINT}/${entryId}`)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '作业票不存在或已归档'
  }
}

function flash(text: string, ok = false) {
  message.value = text
  messageOk.value = ok
}

async function runDetailAction(action: string) {
  const params: ActionParams = { action }
  if (action === ACTIONS.reject) {
    const reason = window.prompt('请填写驳回原因（安全条件不满足的具体项）')
    if (reason === null) return
    params['说明'] = reason
  }
  if (action === ACTIONS.postpone) {
    if (!entry.value) return
    postponeForm['新有效期起'] = entry.value['有效期起']
    postponeForm['新有效期止'] = entry.value['有效期止']
    postponeForm['说明'] = ''
    formError.value = ''
    postponing.value = true
    return
  }
  if (!window.confirm(`确认执行「${action}」？`)) return
  try {
    const result = await runPermitAction(entryId, params)
    flash(result.message, result.ok)
    await load()
  } catch (error) {
    flash(error instanceof Error ? error.message : '操作失败', false)
  }
}

async function submitPostpone() {
  formError.value = ''
  try {
    const result = await runPermitAction(entryId, { action: ACTIONS.postpone, ...postponeForm })
    if (!result.ok) {
      formError.value = result.message
      return
    }
    postponing.value = false
    flash(result.message, true)
    await load()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '延期失败'
  }
}

onMounted(load)
</script>
