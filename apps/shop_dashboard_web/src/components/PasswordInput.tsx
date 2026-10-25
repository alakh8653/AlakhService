import { forwardRef, useState, type InputHTMLAttributes } from 'react';
import { Eye, EyeOff } from 'lucide-react';

/** A password box with a show/hide button, handy when typing on a phone keyboard. */
const PasswordInput = forwardRef<HTMLInputElement, Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>>(
  function PasswordInput({ className = '', ...props }, ref) {
    const [visible, setVisible] = useState(false);
    return (
      <div className="relative">
        <input ref={ref} type={visible ? 'text' : 'password'} className={`${className} pr-11`} {...props} />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-700 rounded-r-lg"
        >
          {visible ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
        </button>
      </div>
    );
  },
);

export default PasswordInput;
