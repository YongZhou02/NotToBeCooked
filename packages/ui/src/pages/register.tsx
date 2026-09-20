import { api, schemas, isApiClientError } from "@workspace/contracts"

import { zodResolver } from "@hookform/resolvers/zod"
import { Controller, useForm } from "react-hook-form"
import z from "zod"
import { Link, useNavigate } from "react-router"
import { useAuth } from "../context/auth-context"
import devToast from "@workspace/ui/lib/alerts"

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Button } from "@workspace/ui/components/button"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "../components/input-group"
import { EyeIcon, EyeOffIcon } from "lucide-react"
import { useState } from "react"

const registerFormSchema = schemas.RegisterRequest.extend({
  email: z.email({ message: "Check email address format (e.g. a@b.c)" }),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
})

export function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const form = useForm<z.infer<typeof registerFormSchema>>({
    resolver: zodResolver(registerFormSchema),
    mode: "onBlur",
    defaultValues: {
      display_name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  })

  /*
  1. Submit the form data
  2. Receives the data. On success hand the token to AuthContext (memory only) and redirect, else
  3. catch errors and set form error
  4. Custom domain error handling  via ApiError, else FastAPI 422 validation error handling
  */
  const onSubmit = async (data: z.infer<typeof registerFormSchema>) => {
    try {
      const response = await api.auth.register({
        display_name: data.display_name,
        email: data.email,
        password: data.password,
      })

      // No devToast(data) here: `data` holds the plaintext password and
      // confirmPassword, and devToast renders whatever it is given.

      // See login.tsx: the access token stays in memory, never in storage.
      login(response.access_token, response.user)
      navigate("/dashboard", { replace: true })
    } catch (err: unknown) {
      if (!isApiClientError(err)) {
        form.setError("root", { message: "An unexpected error occurred" })
        devToast(err)
        return
      }

      if (err.code === "EMAIL_EXISTS") {
        form.setError("email", { message: err.message })
      } else if (err.detail) {
        err.detail.forEach((issue) => {
          const fieldName = issue.loc[1] as "email" | "password"
          form.setError(fieldName, { message: issue.msg })
        })
      } else {
        form.setError("root", { message: err.message })
      }
      devToast(err)
    }
  }

  const rootError = form.formState.errors.root?.message

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md border border-border shadow-xl">
        <CardHeader className="flex flex-col items-center space-y-2 text-center">
          <img
            src="/ntbc-logo.png"
            alt="NotToBeCooked Logo"
            className="h-12 w-12 rounded-xl object-contain shadow-md"
          />
          <div>
            <CardTitle className="text-2xl font-bold tracking-tight">
              Create an Account
            </CardTitle>
            <CardDescription>
              Register your RAG study account to get started
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Global/Server Error Banner */}
          {rootError && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/20 bg-destructive/15 p-3.5 text-sm font-medium text-destructive"
            >
              {rootError}
            </div>
          )}

          <form
            id="form-register"
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4"
          >
            <FieldGroup>
              {/* Display Name */}
              <Controller
                name="display_name"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor={field.name}>Display Name</FieldLabel>
                    <div className="relative w-full">
                      <Input
                        {...field}
                        id={field.name}
                        type="text"
                        aria-invalid={fieldState.invalid}
                        placeholder="John Doe"
                        autoComplete="name"
                      />
                    </div>
                    {fieldState.invalid && (
                      <FieldError errors={[fieldState.error]} />
                    )}
                  </Field>
                )}
              />

              {/* Email Field */}
              <Controller
                name="email"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor={field.name}>Email Address</FieldLabel>
                    <div className="relative w-full">
                      <Input
                        {...field}
                        id={field.name}
                        type="text"
                        inputMode="email"
                        aria-invalid={fieldState.invalid}
                        placeholder="example@gmail.com"
                        autoComplete="email"
                      />
                    </div>
                    {fieldState.invalid && (
                      <FieldError errors={[fieldState.error]} />
                    )}
                  </Field>
                )}
              />

              {/* Password Field */}
              <Controller
                name="password"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor={field.name}>Password</FieldLabel>
                    <InputGroup>
                      <InputGroupInput
                        {...field}
                        id={field.name}
                        type={showPassword ? "text" : "password"}
                        aria-invalid={fieldState.invalid}
                        placeholder="••••••••"
                        autoComplete="new-password"
                      />
                      <InputGroupAddon align="inline-end">
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                        >
                          {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                        </button>
                      </InputGroupAddon>
                    </InputGroup>
                    {fieldState.invalid ? (
                      <FieldError errors={[fieldState.error]} />
                    ) : (
                      // The rules live in the contract -- RegisterRequest
                      // .password carries minLength 8 and pattern .*[A-Z].*,
                      // and the generated zod schema checks both. This line
                      // only states them before the user types, which is the
                      // half a schema cannot do. r80.
                      <FieldDescription>
                        At least 8 characters, including one capital letter.
                      </FieldDescription>
                    )}
                  </Field>
                )}
              />

              {/* Confirm Password Field */}
              <Controller
                name="confirmPassword"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor={field.name}>
                      Confirm Password
                    </FieldLabel>
                    <Input
                      {...field}
                      id={field.name}
                      type={showPassword ? "text" : "password"}
                      aria-invalid={fieldState.invalid}
                      placeholder="••••••••"
                      autoComplete="new-password"
                    />
                    {fieldState.invalid && (
                      <FieldError errors={[fieldState.error]} />
                    )}
                  </Field>
                )}
              />
            </FieldGroup>
          </form>
        </CardContent>

        <CardFooter className="flex flex-col gap-4 pt-2">
          <Button
            type="submit"
            form="form-register"
            size="lg"
            className="w-full font-semibold"
            disabled={form.formState.isSubmitting}
          >
            {form.formState.isSubmitting ? "Creating Account..." : "Register"}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-semibold text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
            >
              Log in
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}

export default RegisterPage
