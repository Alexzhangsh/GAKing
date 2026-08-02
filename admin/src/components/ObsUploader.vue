<!-- @ai-generated -->
<template>
  <div class="obs-uploader">
    <div class="upload-area" @click="triggerUpload" @drop.prevent="handleDrop" @dragover.prevent>
      <div v-if="!modelValue" class="upload-placeholder">
        <el-icon class="upload-icon"><Upload /></el-icon>
        <span>点击或拖拽上传文件</span>
        <span class="upload-tip">支持 jpg、png、gif、pdf 等格式，单文件不超过 10MB</span>
      </div>
      <div v-else class="upload-preview">
        <div v-if="isImage" class="image-preview">
          <img :src="modelValue" alt="预览" />
          <div class="preview-overlay">
            <el-button size="small" type="danger" @click.stop="handleRemove">删除</el-button>
          </div>
        </div>
        <div v-else class="file-preview">
          <el-icon class="file-icon"><Document /></el-icon>
          <span>{{ getFileName(modelValue) }}</span>
          <el-button size="small" type="danger" @click.stop="handleRemove">删除</el-button>
        </div>
      </div>
    </div>
    <input ref="fileInputRef" type="file" :accept="accept" class="file-input" @change="handleFileChange" />
    <el-progress v-if="uploading" :percentage="progress" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElIcon, ElButton, ElProgress, ElMessage } from 'element-plus'
import { Upload, Document } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  modelValue: string
  accept?: string
  maxSize?: number
}>(), {
  accept: 'image/*',
  maxSize: 10240
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const progress = ref(0)

const isImage = computed(() => {
  if (!props.modelValue) return false
  const ext = props.modelValue.split('.').pop()?.toLowerCase()
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext || '')
})

const triggerUpload = () => {
  if (uploading.value || props.modelValue) return
  fileInputRef.value?.click()
}

const handleDrop = (e: DragEvent) => {
  if (uploading.value || props.modelValue) return
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFiles(files)
  }
}

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    handleFiles(files)
  }
  target.value = ''
}

const handleFiles = async (files: FileList) => {
  const file = files[0]
  if (!file) return

  if (file.size > props.maxSize * 1024) {
    ElMessage.error(`文件大小不能超过 ${props.maxSize}KB`)
    return
  }

  await uploadFile(file)
}

const uploadFile = async (file: File) => {
  uploading.value = true
  progress.value = 0

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
      emit('update:modelValue', result.data.url)
      ElMessage.success('上传成功')
    } else {
      throw new Error(result.message || '上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
    progress.value = 0
  }
}

const handleRemove = () => {
  emit('update:modelValue', '')
}

const getFileName = (url: string) => {
  const parts = url.split('/')
  return parts[parts.length - 1] || '未命名文件'
}
</script>

<style scoped>
.obs-uploader {
  width: 100%;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.upload-area:hover {
  border-color: #409eff;
  background-color: #f5f7fa;
}

.upload-area.dragover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
}

.upload-placeholder span {
  font-size: 14px;
  color: #606266;
}

.upload-tip {
  font-size: 12px !important;
  color: #909399 !important;
}

.upload-preview {
  display: flex;
  justify-content: center;
  align-items: center;
}

.image-preview {
  position: relative;
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  overflow: hidden;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px;
  display: flex;
  justify-content: center;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: #f5f7fa;
  border-radius: 8px;
}

.file-icon {
  font-size: 32px;
  color: #409eff;
}

.file-preview span {
  font-size: 14px;
  color: #606266;
}

.file-input {
  display: none;
}
</style>