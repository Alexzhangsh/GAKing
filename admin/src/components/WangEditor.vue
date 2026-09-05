<!-- @ai-generated -->
<template>
  <div class="wangeditor-container" :class="{ 'is-disabled': disabled }">
    <div ref="toolbarRef" class="wangeditor-toolbar"></div>
    <div ref="editorRef" class="wangeditor-content" :style="{ height: height + 'px' }"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import '@wangeditor/editor/dist/css/style.css'
import { createEditor, createToolbar } from '@wangeditor/editor'
import type { IDomEditor, IToolbarConfig } from '@wangeditor/editor'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
  height?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const toolbarRef = ref<HTMLDivElement | null>(null)
const editorRef = ref<HTMLDivElement | null>(null)
/** 编辑器实例用 shallowRef 避免 deep ref 代理干扰内部状态 */
const editor = shallowRef<IDomEditor | null>(null)
let toolbar: ReturnType<typeof createToolbar> | null = null
/** 标记内部同步，防止 setHtml 触发 change 造成回环 */
let innerSync = false

const toolbarConfig: Partial<IToolbarConfig> = {
  toolbarKeys: [
    'bold',
    'italic',
    'underline',
    {
      key: 'group-more-style',
      title: '更多样式',
      iconSvg: '<svg viewBox="0 0 1024 1024"></svg>',
      menuKeys: ['through', 'color', 'bgColor'],
    },
    {
      key: 'group-justify',
      title: '对齐',
      iconSvg: '<svg viewBox="0 0 1024 1024"></svg>',
      menuKeys: ['justifyLeft', 'justifyCenter', 'justifyRight'],
    },
    '|',
    {
      key: 'group-head',
      title: '标题',
      iconSvg: '<svg viewBox="0 0 1024 1024"></svg>',
      menuKeys: ['header1', 'header2', 'header3'],
    },
    'fontSize',
    'fontFamily',
    'lineHeight',
    '|',
    {
      key: 'group-list',
      title: '列表',
      iconSvg: '<svg viewBox="0 0 1024 1024"></svg>',
      menuKeys: ['bulletedList', 'numberedList'],
    },
    'todo',
    '|',
    'blockquote',
    'code',
    'insertLink',
    'uploadImage',
    'insertVideo',
    'divider',
    '|',
    'undo',
    'redo',
    '|',
    'fullScreen'
  ],
  excludeKeys: []
}

const createEditorInstance = () => {
  if (!editorRef.value || !toolbarRef.value) return

  const instance = createEditor({
    selector: editorRef.value,
    config: {
      placeholder: '请输入消息内容，支持占位符 {{keyword1}}',
      readOnly: props.disabled || false,
      MENU_CONF: {
        uploadImage: {
          customUpload: async (file: File) => {
            return customUpload(file)
          }
        },
        uploadVideo: {
          customUpload: async (file: File) => {
            return customUpload(file)
          }
        }
      }
    }
  })
  editor.value = instance

  // 初始化内容
  if (props.modelValue) {
    innerSync = true
    instance.setHtml(props.modelValue)
    innerSync = false
  }

  toolbar = createToolbar({
    editor: instance,
    selector: toolbarRef.value,
    config: toolbarConfig
  })

  instance.on('change', () => {
    if (innerSync) return
    const html = instance.getHtml()
    emit('update:modelValue', html)
  })
}

const customUpload = async (file: File): Promise<{ url: string }> => {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch('/api/admin/upload', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${localStorage.getItem('admin_token')}`
      },
      body: formData
    })

    const result = await response.json()
    if (result.code === 0 && result.data) {
      return { url: result.data.url }
    } else {
      throw new Error('上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    throw error
  }
}

watch(
  () => props.modelValue,
  (newVal) => {
    const instance = editor.value
    if (instance && newVal !== instance.getHtml()) {
      innerSync = true
      instance.setHtml(newVal)
      innerSync = false
    }
  }
)

watch(
  () => props.disabled,
  (newVal) => {
    const instance = editor.value
    if (instance) {
      instance.disable()
      if (!newVal) instance.enable()
    }
  }
)

onMounted(() => {
  createEditorInstance()
})

onBeforeUnmount(() => {
  if (toolbar) {
    toolbar.destroy()
    toolbar = null
  }
  const instance = editor.value
  if (instance) {
    instance.destroy()
    editor.value = null
  }
})

/** 暴露 editor 实例，供父组件直接调用 insertText / focus 等方法 */
defineExpose({ editor })
</script>

<style scoped>
.wangeditor-container {
  width: 100%;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.wangeditor-toolbar {
  border-bottom: 1px solid #e8e8e8;
}

.wangeditor-content {
  overflow-y: auto;
}

.wangeditor-container.is-disabled {
  opacity: 0.7;
  pointer-events: none;
}
</style>