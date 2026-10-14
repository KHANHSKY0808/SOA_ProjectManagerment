import { normalizeApiError } from '../../services/api-error'

export function registrationError(cause: unknown): string {
  const error = normalizeApiError(cause)
  const code = error.details && typeof error.details === 'object' && 'code' in error.details
    ? String(error.details.code) : ''
  const messages: Record<string, string> = {
    topic_closed: 'Đề tài đã đóng đăng ký. Vui lòng tải lại danh sách.',
    topic_registration_closed: 'Đề tài đã đóng đăng ký. Bạn không thể hủy đăng ký này.',
    faculty_mismatch: 'Đề tài không thuộc khoa của bạn. Vui lòng chọn đề tài khác.',
    registration_conflict: 'Bạn đã có đăng ký hiện tại hoặc dữ liệu đã thay đổi. Hãy kiểm tra kết quả.',
    dependency_unavailable: 'Dịch vụ tra cứu tạm thời không khả dụng. Vui lòng thử lại sau.',
    storage_unavailable: 'Dịch vụ đăng ký đang bận. Vui lòng kiểm tra kết quả trước khi thử lại.',
  }
  if (messages[code]) return messages[code]
  if (error.status === 400) return 'Thông tin đăng ký không hợp lệ. Vui lòng kiểm tra đề tài và học kỳ.'
  if (error.status === 403) return 'Bạn không có quyền hoặc hồ sơ sinh viên chưa có khoa hợp lệ.'
  if (error.status === 404) return 'Đề tài hoặc đăng ký không còn tồn tại. Vui lòng tải lại dữ liệu.'
  if (error.status === 409) return messages.registration_conflict
  if (error.status === 503) return 'Dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau.'
  return error.message
}

export function requiresReconciliation(cause: unknown, cancellation: boolean): boolean {
  const error = normalizeApiError(cause)
  if (error.details && typeof error.details === 'object' && 'code' in error.details &&
      error.details.code === 'topic_registration_closed') return false
  return ['network', 'timeout', 'unknown'].includes(error.kind) || (error.status ?? 0) >= 500 ||
    error.status === 409 || (cancellation && error.status === 404)
}
