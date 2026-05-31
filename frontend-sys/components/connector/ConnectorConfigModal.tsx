'use client';

import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { FaTelegram } from 'react-icons/fa';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Field, FieldLabel, FieldContent, FieldError, FieldDescription } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Loader } from '@/components/ui/Loader';
import { TelegramConnectorConfig } from '@/types/connectors';

interface ConnectorConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (config: TelegramConnectorConfig) => Promise<void>;
  isSubmitting: boolean;
}

const telegramSchema = z.object({
  botUsername: z.string()
    .min(3, 'Bot username must be at least 3 characters')
    .regex(/^[a-zA-Z0-9_]+$/, 'Username can only contain letters, numbers, and underscores')
    .refine((val) => val.toLowerCase().endsWith('bot'), 'Bot username must end in "bot" (e.g. SalesBot)'),
  accessToken: z.string()
    .min(20, 'Token is too short')
    .refine((val) => val.includes(':'), 'Token must contain a colon separator (e.g. 123456:ABC-DEF...)')
    .refine((val) => !val.includes(' '), 'Token cannot contain spaces'),
});

type TelegramFormValues = z.infer<typeof telegramSchema>;

export const ConnectorConfigModal: React.FC<ConnectorConfigModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TelegramFormValues>({
    resolver: zodResolver(telegramSchema),
    defaultValues: {
      botUsername: '',
      accessToken: '',
    },
  });

  // Reset form when modal state changes
  useEffect(() => {
    if (!isOpen) {
      reset({
        botUsername: '',
        accessToken: '',
      });
    }
  }, [isOpen, reset]);

  const onFormSubmit = async (data: TelegramFormValues) => {
    try {
      await onSubmit(data);
      onClose();
    } catch (err) {
      console.error('Failed to configure Telegram bot:', err);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl p-6">
        <DialogHeader className="space-y-3">
          <div className="w-10 h-10 rounded-xl bg-[#2AABEE] text-white flex items-center justify-center text-lg shadow-md">
            <FaTelegram className="size-5" />
          </div>
          <div>
            <DialogTitle className="text-base font-bold text-slate-900 dark:text-zinc-100">
              Connect Telegram Bot
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 dark:text-zinc-400 mt-1">
              Provide your Telegram bot username and HTTP API token. To create a bot, contact{' '}
              <a
                href="https://t.me/botfather"
                target="_blank"
                rel="noreferrer"
                className="text-[#2AABEE] font-semibold hover:underline"
              >
                @BotFather
              </a>{' '}
              on Telegram.
            </DialogDescription>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-5 py-2">
          {/* Bot Username Field */}
          <Field>
            <FieldLabel htmlFor="botUsername" className="text-xs font-semibold text-slate-700 dark:text-zinc-300">
              Bot Username
            </FieldLabel>
            <FieldContent>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400 font-medium">
                  @
                </span>
                <Input
                  id="botUsername"
                  type="text"
                  placeholder="MySalesBot"
                  className="pl-7"
                  disabled={isSubmitting}
                  aria-invalid={!!errors.botUsername}
                  {...register('botUsername')}
                />
              </div>
              <FieldDescription className="text-[10px] text-slate-400 dark:text-zinc-500 mt-0.5">
                The public username of your bot (must end with &quot;bot&quot;).
              </FieldDescription>
              {errors.botUsername && (
                <FieldError className="text-[11px] font-medium text-red-500 mt-1">
                  {errors.botUsername.message}
                </FieldError>
              )}
            </FieldContent>
          </Field>

          {/* Access Token Field */}
          <Field>
            <FieldLabel htmlFor="accessToken" className="text-xs font-semibold text-slate-700 dark:text-zinc-300">
              HTTP API Token (Access Token)
            </FieldLabel>
            <FieldContent>
              <Input
                id="accessToken"
                type="password"
                placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                disabled={isSubmitting}
                aria-invalid={!!errors.accessToken}
                {...register('accessToken')}
              />
              <FieldDescription className="text-[10px] text-slate-400 dark:text-zinc-500 mt-0.5">
                Keep this token private. It is used to fetch incoming channel messages.
              </FieldDescription>
              {errors.accessToken && (
                <FieldError className="text-[11px] font-medium text-red-500 mt-1">
                  {errors.accessToken.message}
                </FieldError>
              )}
            </FieldContent>
          </Field>

          <DialogFooter className="mt-6 flex flex-row justify-end gap-2 border-t pt-4 border-zinc-100 dark:border-zinc-800">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              size="sm"
              className="bg-[#2AABEE] text-white hover:bg-[#229ED9] hover:border-[#229ED9]"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <Loader size="sm" text="Verifying" className="text-white" />
              ) : (
                'Save Connection'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
