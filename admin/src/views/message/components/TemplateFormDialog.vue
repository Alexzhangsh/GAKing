<!-- @ai-generated -->
<!--
  消息模板编辑弹窗（F04-1 富文本增强版）
  - 消息内容使用富文本编辑器（wangEditor）
  - 占位符快捷插入 + 实时可视化预览
  - 支持实时调整关键词示例值
  - 支持新增/编辑两种模式
-->
<template>
  <el-dialog
    :model-value="visible"
    :title="dialogTitle"
    width="760px"
    top="6vh"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="模板名称" prop="template_name">
        <el-input v-model="form.template_name" placeholder="请输入模板名称" maxlength="128" :disabled="readonly" />
      </el-form-item>
      <el-form-item label="模板类型" prop="template_type">
        <el-radio-group v-model="form.template_type" :disabled="readonly">
          <el-radio :value="1">微信订阅消息</el-radio>
          <el-radio :value="2">站内消息/公告</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.template_type === 1" label="模板ID(tmpl_id)" prop="tmpl_id">
        <el-input v-model="form.tmpl_id" placeholder="微信订阅消息模板ID" maxlength="128" :disabled="readonly" />
      </el-form-item>
      <el-form-item label="消息标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入消息标题" maxlength="256" :disabled="readonly" />
      </el-form-item>
      <el-form-item label="消息内容" prop="content">
        <div class="content-editor">
          <!-- 占位符快捷插入（只读模式隐藏） -->
          <div v-if="!readonly" class="placeholder-bar">
            <span class="placeholder-label">插入占位符：</span>
            <el-tag
              v-for="ph in QUICK_PLACEHOLDERS"
              :key="ph"
              class="placeholder-tag"
              size="small"
              effect="plain"
              @click="insertPlaceholder(ph)"
            >
              {{ ph }}
            </el-tag>
            <el-popover placement="bottom-start" :width="240" trigger="click">
              <template #reference>
                <el-button size="small" text type="primary">自定义</el-button>
              </template>
              <div class="custom-ph">
                <el-input
                  v-model="customPhName"
                  size="small"
                  placeholder="占位符名称，如 nickname"
                  maxlength="30"
                  @keyup.enter="insertCustomPlaceholder"
                />
                <el-button size="small" type="primary" style="margin-top: 8px" @click="insertCustomPlaceholder">
                  插入 {{ customPhLabel }}
                </el-button>
              </div>
            </el-popover>
            <span class="placeholder-hint">点击插入到光标处，预览时替换为示例值</span>
          </div>
          <WangEditor
            ref="editorRef"
            v-model="form.content"
            :height="240"
            :disabled="readonly"
          />
        </div>
      </el-form-item>
      <el-form-item v-if="form.template_type === 1" label="关键词列表">
        <div class="keywords-area">
          <el-tag
            v-for="(kw, idx) in form.keywords"
            :key="idx"
            :closable="!readonly"
            @close="form.keywords!.splice(idx, 1)"
            class="keyword-tag"
          >
            {{ kw }}
          </el-tag>
          <template v-if="!readonly">
            <el-input
              v-if="keywordInputVisible"
              ref="keywordInputRef"
              v-model="keywordInputValue"
              size="small"
              style="width: 120px"
              @keyup.enter="addKeyword"
              @blur="addKeyword"
            />
            <el-button v-else size="small" @click="showKeywordInput">+ 关键词</el-button>
          </template>
        </div>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注说明" maxlength="512" :disabled="readonly" />
      </el-form-item>
      <!-- 实时预览区 -->
      <el-form-item label="消息预览">
        <div class="preview-area">
          <div class="preview-toolbar">
            <span class="preview-title-label">实时预览</span>
            <el-tag v-if="placeholderNames.length" size="small" type="warning" effect="light">
              {{ placeholderNames.length }} 个占位符
            </el-tag>
            <el-tag v-else size="small" type="info" effect="plain">无占位符</el-tag>
          </div>
          <!-- 占位符示例值调整 -->
          <div v-if="placeholderNames.length && !readonly" class="sample-adjust">
            <div class="sample-adjust-title">关键词示例值（可实时调整，预览即时更新）</div>
            <div class="sample-adjust-grid">
              <div v-for="name in placeholderNames" :key="name" class="sample-item">
                <span class="sample-name">{{ name }}</span>
                <el-input
                  v-model="sampleMap[name]"
                  size="small"
                  :placeholder="`默认：${sampleValue(name)}`"
                  @input="syncSampleMap"
                />
              </div>
            </div>
          </div>
          <div class="preview-body">
            <div class="preview-title">{{ form.title || '（未设置标题）' }}</div>
            <div class="preview-content" v-html="previewHtml"></div>
            <div v-if="form.template_type === 1" class="preview-meta">
              <el-tag size="small" type="info">微信订阅消息</el-tag>
              <el-tag v-if="form.tmpl_id" size="small" type="info">tmpl_id: {{ form.tmpl_id }}</el-tag>
              <el-tag v-if="form.keywords && form.keywords.length" size="small" type="warning">
                {{ form.keywords.length }} 个关键词
              </el-tag>
            </div>
            <div v-else class="preview-meta">
              <el-tag size="small" type="info">站内消息/公告</el-tag>
            </div>
          </div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <template v-if="readonly">
        <el-button type="primary" @click="$emit('update:visible', false)">关闭</el-button>
      </template>
      <template v-else>
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, nextTick, watch } from 'vue'
import {
  ElDialog, ElForm, ElFormItem, ElInput, ElRadioGroup, ElRadio,
  ElButton, ElTag, ElMessage, ElPopover, type FormInstance,
} from 'element-plus'
import WangEditor from '@/components/WangEditor.vue'
import {
  messageTemplateApi,
  type MessageTemplate,
  type MessageTemplateCreate,
  type MessageTemplateUpdate,
} from '@/api/message'
import {
  renderTemplatePreview,
  sanitizeHtml,
  stripHtml,
  extractPlaceholders,
  sampleValue,
} from '@/utils/messagePreview'

const props = defineProps<{
  visible: boolean
  editData?: MessageTemplate | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'success'): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => !!props.editData)
const readonly = computed(() => props.readonly === true)
const dialogTitle = computed(() => {
  if (readonly.value) return '查看消息模板'
  return isEdit.value ? '编辑消息模板' : '新增消息模板'
})

const form = reactive<MessageTemplateCreate>({
  template_name: '',
  template_type: 1,
  tmpl_id: '',
  title: '',
  content: '',
  keywords: [],
  remark: '',
})

// ── 占位符快捷插入 ──────────────────────────────
const QUICK_PLACEHOLDERS = ['keyword1', 'keyword2', 'keyword3', 'order_id', 'amount', 'goods_name', 'remark']
const editorRef = ref<InstanceType<typeof WangEditor>>()
const customPhName = ref('')
const customPhLabel = computed(() => {
  const name = customPhName.value.trim()
  return name ? `{{${name}}}` : ''
})

function insertPlaceholder(name: string) {
  const inst = editorRef.value?.editor
  if (inst) {
    inst.insertText(`{{${name}}}`)
    inst.focus()
  } else {
    // 编辑器未就绪时追加到内容末尾
    form.content = `${form.content || ''}{{${name}}}`
  }
}

function insertCustomPlaceholder() {
  const name = customPhName.value.trim()
  if (!name) {
    ElMessage.warning('请输入占位符名称')
    return
  }
  if (!/^[\w\u4e00-\u9fa5]+$/.test(name)) {
    ElMessage.warning('占位符名称仅支持字母、数字、下划线、中文')
    return
  }
  insertPlaceholder(name)
  customPhName.value = ''
}

// ── 表单校验 ──────────────────────────────
const rules = {
  template_name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  template_type: [{ required: true, message: '请选择模板类型', trigger: 'change' }],
  content: [{
    validator: (_rule: unknown, _value: string, callback: (err?: Error) => void) => {
      if (!stripHtml(form.content || '')) {
        callback(new Error('请输入消息内容'))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
  tmpl_id: [{
    validator: (_rule: unknown, _value: string, callback: (err?: Error) => void) => {
      if (form.template_type === 1 && !form.tmpl_id) {
        callback(new Error('微信订阅消息模板必须填写 tmpl_id'))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
}

// ── 占位符提取 + 示例值管理 ──────────────────────────────
const placeholderNames = ref<string[]>([])
const sampleMap = reactive<Record<string, string>>({})

/** 从内容重新提取占位符，保留已有自定义示例值 */
function syncPlaceholders() {
  const names = extractPlaceholders(form.content || '')
  placeholderNames.value = names
  for (const name of names) {
    if (!(name in sampleMap)) {
      sampleMap[name] = ''
    }
  }
  // 清理已不存在的占位符示例值
  for (const key of Object.keys(sampleMap)) {
    if (!names.includes(key)) {
      delete sampleMap[key]
    }
  }
}

function syncSampleMap() {
  // 输入时强制触发预览重算（reactive 已自动，此处保留占位）
}

/** 实时预览：占位符替换为示例值 + HTML 消毒 */
const previewHtml = computed(() => {
  const html = renderTemplatePreview(form.content || '', sampleMap)
  return sanitizeHtml(html)
})

// 内容变化时同步占位符
watch(
  () => form.content,
  () => syncPlaceholders(),
)

// 关键词输入
const keywordInputVisible = ref(false)
const keywordInputValue = ref('')
const keywordInputRef = ref<InstanceType<typeof ElInput>>()

function showKeywordInput() {
  keywordInputVisible.value = true
  nextTick(() => keywordInputRef.value?.focus())
}

function addKeyword() {
  const val = keywordInputValue.value.trim()
  if (val && !form.keywords?.includes(val)) {
    form.keywords = [...(form.keywords || []), val]
  }
  keywordInputVisible.value = false
  keywordInputValue.value = ''
}

// 编辑模式回填
watch(() => props.visible, (val) => {
  if (val && props.editData) {
    Object.assign(form, {
      template_name: props.editData.template_name,
      template_type: props.editData.template_type,
      tmpl_id: props.editData.tmpl_id,
      title: props.editData.title,
      content: props.editData.content,
      keywords: props.editData.keywords ? [...props.editData.keywords] : [],
      remark: props.editData.remark,
    })
  } else if (val) {
    Object.assign(form, {
      template_name: '', template_type: 1, tmpl_id: '',
      title: '', content: '', keywords: [], remark: '',
    })
  }
  // 重置示例值
  for (const key of Object.keys(sampleMap)) {
    delete sampleMap[key]
  }
  placeholderNames.value = []
  customPhName.value = ''
  nextTick(() => syncPlaceholders())
})

async function handleSubmit() {
  if (readonly.value) return
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value && props.editData) {
        const updateData: MessageTemplateUpdate = {
          template_name: form.template_name,
          template_type: form.template_type,
          tmpl_id: form.tmpl_id,
          title: form.title,
          content: form.content,
          keywords: form.keywords,
          remark: form.remark,
        }
        await messageTemplateApi.update(props.editData.id, updateData)
        ElMessage.success('更新成功')
      } else {
        await messageTemplateApi.create(form)
        ElMessage.success('创建成功')
      }
      emit('update:visible', false)
      emit('success')
    } catch {
      // 拦截器已提示
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.content-editor {
  width: 100%;
}

.placeholder-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.placeholder-label {
  font-size: 12px;
  color: #909399;
  margin-right: 2px;
}

.placeholder-tag {
  cursor: pointer;
  margin: 0;
}

.placeholder-tag:hover {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.placeholder-hint {
  font-size: 12px;
  color: #c0c4cc;
  margin-left: 4px;
}

.custom-ph {
  display: flex;
  flex-direction: column;
}

.keywords-area {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.keyword-tag {
  margin: 0;
}

.preview-area {
  width: 100%;
}

.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.preview-title-label {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.sample-adjust {
  margin-bottom: 8px;
  padding: 8px 12px;
  border: 1px dashed #e4e7ed;
  border-radius: 6px;
  background: #fcfcfd;
}

.sample-adjust-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.sample-adjust-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sample-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sample-name {
  font-size: 12px;
  color: #606266;
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.preview-body {
  margin-top: 8px;
  padding: 12px 16px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
  width: 100%;
}

.preview-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
}

.preview-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
  word-break: break-all;
  margin: 0 0 8px;
}

.preview-content :deep(img) {
  max-width: 100%;
}

.preview-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  border-top: 1px dashed #e4e7ed;
  padding-top: 8px;
}
</style>