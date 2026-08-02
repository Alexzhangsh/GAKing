<!-- @ai-generated -->
<template>
  <div class="wangeditor-container">
    <div ref="editorRef" style="height: 400px; border: 1px solid #e8e8e8;"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import '@wangeditor/editor/dist/css/style.css'
import { createEditor, createToolbar, IDomEditor, IToolbarConfig } from '@wangeditor/editor'
import type { Editor } from '@wangeditor/editor'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const editorRef = ref<HTMLDivElement | null>(null)
let editor: Editor | null = null
let toolbar: ReturnType<typeof createToolbar> | null = null

const toolbarConfig: Partial<IToolbarConfig> = {
  toolbarKeys: [
    'bold',
    'italic',
    'underline',
    'strikethrough',
    'color',
    'bgColor',
    '|',
    'head',
    'fontSize',
    'fontFamily',
    'lineHeight',
    '|',
    'list',
    'todo',
    'justify',
    '|',
    'quote',
    'code',
    'link',
    'image',
    'video',
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
  if (!editorRef.value) return

  editor = createEditor({
    selector: editorRef.value,
    config: {
      placeholder: '请输入内容',
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
    },
    content: props.modelValue
  })

  toolbar = createToolbar({
    editor,
    selector: '',
    config: toolbarConfig
  })

  editor.on('change', () => {
    if (editor) {
      const html = editor.getHtml()
      emit('update:modelValue', html)
    }
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

watch(() => props.modelValue, (newVal) => {
  if (editor && newVal !== editor.getHtml()) {
    editor.setHtml(newVal)
  }
})

watch(() => props.disabled, (newVal) => {
  if (editor) {
    editor.setConfig({ readOnly: newVal || false })
  }
})

onMounted(() => {
  createEditorInstance()
})

onBeforeUnmount(() => {
  if (toolbar) {
    toolbar.destroy()
    toolbar = null
  }
  if (editor) {
    editor.destroy()
    editor = null
  }
})
</script>

<style scoped>
.wangeditor-container {
  width: 100%;
}
</style>